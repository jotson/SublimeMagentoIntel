# Magento Intel

This is a naive completion plugin for Magento.

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

Auto complete by pressing `Ctrl/Cmd+space` immediately following ->. Select one of the choices and you'll even get parameters you can tab through.

This is all done dynamically so nothing needs to be scanned before the system starts working. And it's quite fast because it only has to stat a few files on each invocation.

It also includes a handy function for opening the source file for any class.
Place the cusor on a class name and press `Ctrl+f5` (Linux/Win) or `Cmd+f5` (OSX). The command is only active within Magento projects.

# Limitations

- This should be considered an early alpha.
- You must be using a project and the root of your project must contain the Magento app folder.
- It only understands _@var $var type_ references and does not go any further than the referenced class (it doesn't follow the inheritance tree).
- It doesn't understand doc strings, @param, class @var, or @return hints. So, the completion only really works at one level.
- It doesn't understand the language so it fails in spectacular fashion in a number of situations, especially when chaining. Check the class names in the auto-complete popup to be sure you're getting completions for the right thing.
- It always assumes that the previous function returns $this for chaining like $model->method1()->method2().
- It uses a naive algorithm for deciding what the class name is for factory methods like Mage::getModel() and Mage::helper(). It does not inspect Magento config.xml files.

Despite all that, it can still be quite handy. Please send pull requests.
