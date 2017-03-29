# plastic-zip-installer
A linux script to install Plastic SCM from the published ZIP bundles.

This program retrieves the ZIP bundles and unpacks them on the default paths. Scripts and config files are automatically generated on first install.

# Usage
As this installer needs to access system paths, administrator privileges are required to run it.

## Arguments
* `--labs`: Uses the _Labs_ section of the Plastic SCM downloads page to check the latest version.
* `--no-upgrade`: Aborts execution if an existing Plastic SCM installation is found.
