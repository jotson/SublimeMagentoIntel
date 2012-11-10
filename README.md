# IMPORTANT!

***This plugin is no longer being developed.*** I've moved all of my efforts over to
[SublimePHPIntel](https://github.com/jotson/SublimePHPIntel). The aim of that
plugin is to replicate all of the functionality you see here and also make it
general purpose for use with any other PHP framework.


# Magento Intel

An auto-complete plugin for Magento.

Given a type hint or a factory method, and based on an understanding of Magento class autoloading, the plugin will find the source file in the current project, scan it for function definitions, and add them to the auto complete popup.

This allows you to complete in situations like this:

    /* @var $v Mage_Catalog_Model_Product */
    $v->{auto complete}

and even:

    Mage::getModel('catalog/product')
        ->load(100)
        ->{auto complete}

It also understands some Magento factories:

    Mage::getModel('catalog/product')->{auto complete}
    Mage::getSingleton('catalog/product')->{auto complete}
    Mage::helper('sales')->{auto complete}


Auto complete by pressing `Ctrl+space` or `Cmd+space` immediately following `->`. Select one of the choices and you'll even get parameters you can tab through.

This is all done dynamically so nothing needs to be scanned before the system starts working. But it's still reasonably fast because it only has to scan a few files on each invocation.

It also includes a handy function for opening the source file for any class.
Place the cusor on a class name and press `Ctrl+f5` (Linux/Win) or `Cmd+f5` (OSX). The command is only active within Magento projects.

# Setup

This plugin requires a command-line version of PHP on your path. It runs PHP's built-in lexical scanner on PHP source files to create a JSON encoded string of tokens to parse.

# Limitations

- No longer under development. Use [SublimePHPIntel](https://github.com/jotson/SublimePHPIntel) instead.
- This should be considered an early alpha.
- You must be using a project and the root of your project must contain the Magento app folder.
- It only understands _@var $var type_, _@returns type_, and _@var type_ hints and doesn't walk the inheritance tree.
- It uses a naive algorithm for deciding what the class name is for factory methods like Mage::getModel() and Mage::helper(). It does not inspect Magento config.xml files.

Despite all that, it can still be quite handy.
