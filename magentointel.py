'''
Copyright 2012 John Watson <https://github.com/jotson>
'''

import os
import re
import sublime
import sublime_plugin


class MagentoComplete(sublime_plugin.EventListener):
    '''
    This is a naive completion plugin for Magento.

    Given a type hint, and based on an understanding of Magento class
    autoloading, the plugin will find the source file referenced by
    a variable in the current project, scan it for function definitions,
    and add them to the auto complete popup.

    This is all done dynamically so nothing needs to be scanned before
    the system starts working. And it's quite fast because it only has
    to stat a couple of files on each invocation.

    This version only understands @var $var type references and does
    not go any further than the referenced class (it doesn't follow
    the inheritance tree).

    It also doesn't understand doc strings, @param, class @var or
    @return values. So, the completion only works at one level.

    Despite that, it can still be quite handy for discovering methods
    available in the Magento core classes.
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

        '''Get variable name to be completed'''
        point = view.sel()[0].a
        source = view.substr(sublime.Region(point - 100, point))
        source = source.split('->')
        source = source[len(source) - 2]
        source = source.split('\n')
        source = source[len(source) - 1]
        source = source.split(' ')
        source = source[len(source) - 1]
        source = source.split('\t')
        source = source[len(source) - 1]
        if not source:
            return data

        '''Scan current file for @var $source to get class'''
        searchtext = source.replace('$', '\$')
        searchtext += ' .* '
        found = view.find('@var ' + searchtext, 0)
        if not found:
            return data

        definition = view.substr(found).lstrip().rstrip()
        className = definition.split(' ')[2]
        if not className:
            return data

        '''Build path to source class'''
        path = self.build_magento_path(className)
        if not path:
            return data

        '''Scan source for functions'''
        functions = self.scan_file(path)
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

        return data

    def scan_file(self, file):
        '''
        Find @var, @param, PHP docs, and function definitions in a file.

        Returns dictionary of completions.
        '''
        retval = {}

        source = open(file, 'r').read()
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
        Build a file path given a Magento class name
        '''
        path = None

        if className == None:
            return

        root = self.get_root_folder()
        if root == None:
            return

        '''
        Look for the class file in app/code then lib
        '''
        if path == None:
            path = [root, 'app', 'code', 'core']
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

        return path

    def get_root_folder(self):
        root = None
        for f in sublime.active_window().folders():
            if os.path.isdir(os.path.join(f, 'app', 'code', 'core', 'Mage')):
                root = f
                break

        return root
