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
import sublime
import sublime_plugin


class MagentoComplete(sublime_plugin.EventListener):
    '''
    Magento auto-completer.
    '''

    def on_query_completions(self, view, prefix, locations):
        data = []

        point = view.sel()[0].a
        if point > 2:
            region = sublime.Region(point - 2, point)
            if view.substr(region) == '->':
                data = self.find_completions(view)

        return (data, sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)

    def find_completions(self, view):
        data = []

        '''
        Scan files for completions for the current context
        '''

        '''Get token to be completed'''
        point = view.sel()[0].a
        tokens = view.substr(sublime.Region(point - 1000, point))
        tokens = re.split('->|\n|\r|\t| ', tokens)
        tokens = tokens[:len(tokens) - 1]
        tokens.reverse()

        className = None
        for token in tokens:
            '''Convert the token to a class name'''
            if token:
                if token.find(';') >= 0:
                    '''
                    Stop at ANY semicolon. This is a bad tokenizer in need of help.
                    '''
                    break

                className = self.convert_token(view, token)
                if className:
                    break

        if not className:
            return data

        '''Build path to source class'''
        path = self.build_magento_path(className)
        if not path:
            return data

        '''Scan source for functions'''
        functions = self.scan_file(file=path, all=token.startswith('$this'))
        if not functions:
            return data

        '''Return snippets'''
        for f in functions.keys():
            name = f
            i = 1
            args = []
            for a in functions[f]:
                a = a.replace('$', '\$')
                args.append('${' + str(i) + ':' + a + '}')
                i += 1

            snippet = '{name}({args})'.format(name=name, args=', '.join(args))

            data.append(tuple([f + '\t' + className, snippet]))

        return sorted(data)

    def convert_token(self, view, token):
        '''
        Given a token, convert it into a Magento class name.

        If the token is a variable (e.g. $var) then we search for @var hints.
        If the token is a Magento factory class, then convert those to Mage_*
            class names.
        '''
        className = None
        token = token.strip()
        if token.startswith('$this'):
            className = re.findall('class (.*)', view.substr(sublime.Region(0, view.size())))[0]
            className.replace('{', '').strip()

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
            className = 'Mage_{m}_Model_{c}'.format(m=cap_first_letter(module), c=cap_first_letter(theclass))

        elif token.startswith('Mage::helper'):
            key = re.findall("\('(.*)'\)", token)
            module = key[0]
            className = 'Mage_{m}_Helper_Data'.format(m=cap_first_letter(module))

        elif token.startswith('Mage::app'):
            className = 'Mage'

        return className

    def scan_file(self, file, all=False):
        '''
        Find @var, @param, PHP docs, and function definitions in a file.

        Returns dictionary of completions.
        '''
        retval = {}

        source = open(file, 'r').read()
        if all:
            functions = re.findall('function (.*?)\((.*)\)', source)
        else:
            functions = re.findall('public function (.*?)\((.*)\)', source)
            functions.extend(re.findall('\s\sfunction (.*?)\((.*)\)', source))
            functions.extend(re.findall('public static function (.*?)\((.*)\)', source))
        for parts in functions:
            name, allargs = parts
            name = name.strip()
            args = []
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
            retval[name] = args

        return retval

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
