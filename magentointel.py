# -*- coding: utf-8 -*-

'''
MagentoIntel plugin for Sublime Text 2
Copyright 2012 John Watson <https://github.com/jotson>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

import os
import re
import glob
import copy
import json
import codecs
import subprocess
import hashlib
#import cProfile, pstats
import sublime
import sublime_plugin


class MagentoComplete(sublime_plugin.EventListener):
    '''
    Magento auto-completer.
    '''

    def __init__(self):
        self.get_all_token_names()

    def on_query_completions(self, view, prefix, locations):
        data = None

        if is_magento():
            point = view.sel()[0].a
            if point > 2:
                region = sublime.Region(point - 2, point)
                if view.substr(region) == '->' or view.substr(region) == '::':
                    #cProfile.runctx('data = self.find_completions(view)', globals(), locals())
                    data = self.find_completions(view)

        if data:
            return (data, sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)
        else:
            return False

    def get_cache_folder(self):
        for f in sublime.active_window().folders():
            folder = f
            break

        if f:
            folder = os.path.join(f, '.magentointel-cache')
            if not os.path.exists(folder):
                os.mkdir(folder)

            return folder

        return None

    def get_all_tokens(self, code=None, cache=True):
        '''
        Use the command-line PHP interpreter to tokenize the code
        '''
        code = code.encode('utf-8')
        
        if cache:
            m = hashlib.md5()
            m.update(code)
            key = m.hexdigest()
            cachefile = os.path.join(self.get_cache_folder(), key)
            if os.path.exists(cachefile):
                tokens = json.loads(codecs.open(cachefile, encoding='utf-8', mode='r').read())
                return tokens

        # This code is a performance bottleneck. Caching helps but there's still a significant delay
        # because the first call to get_all_tokens with the partial code up to the cursor can't be
        # cached.
        code = code.replace("'", "\\'")
        php = "echo json_encode(token_get_all('{code}'));".format(code=code)
        tokens = subprocess.Popen(['php', '-r', php], bufsize=1, stdout=subprocess.PIPE, shell=False).communicate()[0]
        tokens = json.loads(tokens)

        if cache and cachefile:
            codecs.open(cachefile, encoding='utf-8', mode='w').write(json.dumps(tokens))

        return tokens

    def get_all_token_names(self):
        '''
        Gets names for all token constants.

        The token constants (http://us2.php.net/manual/en/tokens.php) values
        aren't consistent between different versions of PHP. The values are
        automatically generated based on PHP's underlying parser infrastructure.
        This code generates a dictionary of token constants from the installed
        version of PHP. The dictionary is later used to convert the token codes
        returned by PHP's token_get_all() into names.
        '''
        self._constants = {}
        self._constants[0] = None
        php = ''
        for i in range(0, 999):
            php += "echo '{code},'.token_name({code}).'|';".format(code=i)
        result = subprocess.Popen(['php', '-r', php], bufsize=1, stdout=subprocess.PIPE, shell=False).communicate()[0]
        for constant in result.split('|'):
            if constant.find(',') >= 0:
                code, name = constant.split(',')
                if name != 'UNKNOWN':
                    self._constants[str(code)] = name

    def get_token_name(self, code):
        '''
        Get name for a given token code.
        '''
        name = None
        code = str(code)
        if code in self._constants:
            name = self._constants[code]
        return name

    def token(self, token):
        '''
        Parse the raw token data into a more consistent form.
        '''
        if type(token).__name__ == 'list':
            kind = self.get_token_name(token[0])
            stmt = token[1]
        else:
            kind = self.get_token_name(0)
            stmt = token

        return kind, stmt

    def get_class(self, tokens):
        '''
        Get the first class definition
        '''
        className = None
        capture_next = False
        for token in tokens:
            kind, stmt = self.token(token)

            if kind == 'T_CLASS':
                # class
                capture_next = True
            elif kind == 'T_STRING' and capture_next:
                className = stmt
                break

        return className

    def get_parent_class(self, tokens):
        '''
        Get the class that the first class definition extends
        '''
        className = None
        capture_next = False
        for token in tokens:
            kind, stmt = self.token(token)

            if kind == 'T_EXTENDS':
                # extends
                capture_next = True
            elif kind == 'T_STRING' and capture_next:
                className = stmt
                break

        return className

    def get_return_class(self, tokens, searchToken):
        '''
        Search tokens for token and return its type.

        When the token is found, return its @var or @return hint
        '''
        className = None
        nest = 0
        for token in tokens:
            kind, stmt = self.token(token)
            if kind == 'T_STRING' and stmt == searchToken and nest == 1:
                break
            if stmt == '{':
                nest += 1
            if stmt == '}':
                nest -= 1
                if nest == 1:
                    className = ''
            if kind == None and stmt == ';' and nest == 1:
                className = ''
            elif kind == 'T_DOC_COMMENT' and nest == 1:
                className = re.findall('@var (.*)', stmt)
                if not className:
                    className = re.findall('@return (.*)', stmt)
                if className:
                    className = className[0].strip()

        print searchToken, 'returns', className
        return className

    def find_completions(self, view):
        '''
        Scan files for completions for the current context
        '''

        data = []

        '''Get token to be completed'''
        point = view.sel()[0].a
        code = view.substr(sublime.Region(0, point))
        tokens = self.get_all_tokens(code=code, cache=False)

        '''
        Convert the token to a class name.

        First, read the list backwards until we get to an enclosing block or
        the previous statement.
        Then create a new token list from that point and iterate forward.
            Get a class name and parse that file for definitions.
                The very first token should be a variable or static class name.
            The next token could be -> or ::.
            Then the next token should be a method name or class member.
            Find the return type or member type.
            Repeat.
        '''
        tokens.reverse()
        nest = 0
        end = 0
        for t in tokens:
            kind, stmt = self.token(t)

            if kind == None and stmt == '(':
                nest += 1
            if kind == None and stmt == ')':
                nest -= 1
            if kind == None and stmt == ';':
                break
            if kind == None and (stmt == '{' or stmt == '}'):
                break
            if nest > 0:
                break
            end += 1

        tokens = tokens[:end]
        tokens.reverse()

        className = None
        nest = 0
        lastToken = None
        lastClass = None
        code = view.substr(sublime.Region(0, view.size()))
        for token in tokens:
            if token:
                kind, stmt = self.token(token)

                thistoken = [kind, stmt]

                if kind == 'T_WHITESPACE':
                    # white space
                    pass
                elif kind == 'T_VARIABLE' and nest == 0:
                    # variable
                    lastToken = thistoken
                elif kind == 'T_STRING' and nest == 0:
                    # string (method or class name)
                    if stmt == 'getModel' or stmt == 'getSingleton' or stmt == 'helper':
                        factory = stmt
                    lastToken = thistoken
                elif kind == None and stmt == '(':
                    nest += 1
                elif kind == None and stmt == ')':
                    nest -= 1
                elif kind == 'T_CONSTANT_ENCAPSED_STRING' and factory:
                    lastToken = ['T_STRING', 'Mage::{factory}({path})'.format(factory=factory, path=stmt)]
                    factory = None
                elif kind == 'T_OBJECT_OPERATOR' and nest == 0:
                    # object operator ->
                    className = self.convert_token(view, code, lastToken[1])
                    if not className:
                        data = []
                elif kind == 'T_DOUBLE_COLON' and nest == 0:
                    # double colon ::
                    className = self.convert_token(view, code, lastToken[1])
                    if not className:
                        className = lastToken[1]

                if not className:
                    continue

                if className == lastClass:
                    continue
                else:
                    data = []

                    lastClass = className

                    '''Build path to source class'''
                    path = self.build_magento_path(className)
                    if not path:
                        return data

                    '''Scan source for functions'''
                    if kind == 'T_DOUBLE_COLON' or lastToken[1] == 'self' or lastToken[1] == 'parent':
                        context = 'static'
                    elif lastToken[1].startswith('$this'):
                        context = 'private'
                    else:
                        context = 'public'
                    symbols, code = self.scan_file(file=path, context=context)
                    if not symbols:
                        return data

                    '''Return snippets'''
                    for f in symbols.keys():
                        name = f
                        i = 1
                        args = []
                        if symbols[f]['kind'] == 'function':
                            for a in symbols[f]['args']:
                                a = a.replace('$', '\$')
                                args.append('${' + str(i) + ':' + a + '}')
                                i += 1

                            snippet = '{name}({args})'.format(name=name, args=', '.join(args))
                        else:
                            snippet = f

                        data.append(tuple([f + '\t' + className, snippet]))

        return sorted(data)

    def convert_token(self, view, code, token):
        '''
        Given a token, convert it into a Magento class name.

        If the token is a variable (e.g. $var) then we search for @var hints.
        If the token is a Magento factory class, then convert those to Mage_*
            class names.
        '''
        className = None
        token = token.strip()

        if token.startswith('$this') or token == 'self':
            tokens = self.get_all_tokens(code)
            className = self.get_class(tokens)

        elif token == 'parent':
            tokens = self.get_all_tokens(code)
            className = self.get_parent_class(tokens)

        elif token.startswith('$'):
            searchtext = token.replace('$', '\$')
            searchtext = searchtext.replace('(', '\(')
            searchtext = searchtext.replace(')', '\)')
            searchtext += ' .* '
            found = view.find('@var ' + searchtext, 0)
            if found:
                definition = view.substr(found).strip()
                className = definition.split(' ')[2]

        elif token.startswith('Mage::getModel') or token.startswith('Mage::getSingleton'):
            key = re.findall("\('(.*)'\)", token)
            (module, theclass) = key[0].split('/')
            className = 'Mage_{m}_Model_'.format(m=cap_first_letter(module))
            classes = []
            for t in theclass.split('_'):
                classes.append(cap_first_letter(t))
            className += '_'.join(classes)

        elif token.startswith('Mage::helper'):
            key = re.findall("\('(.*)'\)", token)
            module = key[0]
            className = 'Mage_{m}_Helper_Data'.format(m=cap_first_letter(module))

        elif token == 'Mage':
            className = 'Mage'

        else:
            tokens = self.get_all_tokens(code)
            className = self.get_return_class(tokens, token)

        return className

    def scan_file(self, file, context='public'):
        '''
        Find @var, @param, PHP docs, and function definitions in a file.

        Returns dictionary of completions.
        '''
        retval = {}

        source = codecs.open(file, encoding='utf-8', mode='r').read()
        if context == 'private':
            symbols = re.findall('(function \w*?)\((.*)\)', source)
            symbols.extend(re.findall('public (\$\w*).*;', source))
            symbols.extend(re.findall('protected (\$\w*).*;', source))
            symbols.extend(re.findall('private (\$\w*).*;', source))
        elif context == 'static':
            symbols = re.findall('public static (function \w*?)\((.*)\)', source)
            symbols.extend(re.findall('(const \w*)=.*;', source))
            symbols.extend(re.findall('public static (\$\w*).*;', source))
        elif context == 'public':
            symbols = re.findall('public (function \w*?)\((.*)\)', source)
            symbols.extend(re.findall('\s\s(function \w*?)\((.*)\)', source))
            symbols.extend(re.findall('public (\$\w*).*;', source))

        for parts in symbols:
            kind = ''
            returnType = ''
            if parts[0].startswith('function'):
                name = parts[0].split(' ')[1]
                allargs = parts[1]
                kind = 'function'
            elif parts.startswith('const'):
                name = parts.split(' ')[1]
                allargs = ''
                kind = 'constant'
            elif parts.startswith('$'):
                name = parts
                allargs = ''
                kind = 'variable'
            name = name.strip()
            args = []
            if kind == 'function':
                for a in allargs.split(','):
                    a = a.strip()
                    t = a.split('=')
                    if len(t) > 1:
                        a = t[0].strip()
                    t = a.split(' ')
                    if len(t) == 1:
                        args.append(t[0].strip())
                    else:
                        args.append(t[1].strip())
            retval[name] = {'kind': kind, 'args': args, 'returnType': returnType}

        return retval, source

    def build_magento_path(self, className):
        '''
        Build a file path given a Magento class name.

        Searches in core, lib, local, and community.
        '''
        path = None

        if className == None:
            return

        root = self.get_root_folder()
        if root == None:
            return

        '''
        Look for the class file in various locations
        '''
        if path == None:
            path = [root, 'app', 'code', 'core']
            path.extend(className.split('_'))
            path = os.path.join(*path) + '.php'
            if not os.path.isfile(path):
                path = None

        if path == None:
            path = [root, 'app']
            path.extend(className.split('_'))
            path = os.path.join(*path) + '.php'
            if not os.path.isfile(path):
                path = None

        if path == None:
            path = [root, 'lib']
            path.extend(className.split('_'))
            path = os.path.join(*path) + '.php'
            if not os.path.isfile(path):
                path = None

        if path == None:
            '''Try community and local folders'''
            folders = ([root, 'app', 'code', 'local'], [root, 'app', 'code', 'community'])
            for path in folders:
                path.extend(className.split('_'))
                path = os.path.join(*path) + '.php'
                if os.path.isfile(path):
                    break
                else:
                    path = None

        if path == None:
            '''
            Imagine an invocation like this: Mage::getModel('module/example').
            The parser will generate a class name of Mage_Module_Model_Example.
            If that class isn't found in any of the above scopes, then we try
            this more intensive search:

            We'll look in all of the local and community folders.
            We'll iterate over all of the folders in each of those folders and
                replace the Mage_ part of the class name with the folder.
                Mage_Module_Model_Example => Folder_Module_Model_Example
            Then we check if that class exists and stop after the first match.
            '''
            folders = ([root, 'app', 'code', 'local'], [root, 'app', 'code', 'community'])
            for origpath in folders:
                newpath = copy.copy(origpath)
                newpath.append('*')
                for folder in glob.glob(os.path.join(*newpath)):
                    c = className.split('_')
                    if c[0] == 'Mage':
                        c[0] = os.path.basename(folder)
                    newpath = copy.copy(origpath)
                    newpath.extend(c)
                    path = os.path.join(*newpath) + '.php'
                    if os.path.isfile(path):
                        break
                    else:
                        path = None
                if path:
                    break

        return path

    def get_root_folder(self):
        '''
        Get the root Magento folder
        '''
        root = None
        for f in sublime.active_window().folders():
            if os.path.isdir(os.path.join(f, 'app', 'code', 'core', 'Mage')):
                root = f
                break

        return root


class MagentoOpenCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        className = view.substr(expand_word(view, view.sel()[0]))
        path = None
        if className:
            path = MagentoComplete.build_magento_path(MagentoComplete(), className)
        if path:
            self.window.open_file(path, sublime.TRANSIENT)
        else:
            sublime.status_message('Select a class name first')

    def is_enabled(self):
        return is_magento()


def expand_word(view, region):
    '''
    Expand the region to hold the entire word it is within
    '''
    start = region.a
    end = region.b
    while re.match('[\w|_]', view.substr(start - 1)):
        start -= 1
    while re.match('[\w|_]', view.substr(end)):
        end += 1

    return sublime.Region(start, end)


def cap_first_letter(word):
    return word[0].upper() + word[1:]


def is_magento():
    for f in sublime.active_window().folders():
        if os.path.isdir(os.path.join(f, 'app', 'code', 'core', 'Mage')):
            return True
    return False
