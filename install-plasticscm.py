#!/usr/bin/env python3

import argparse
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import tarfile
import zipfile
from io import BytesIO
from urllib.request import urlopen


class Uris:
    Download = "https://www.plasticscm.com/download"
    Labs = "{}/labs".format(Download)
    Mono = "http://www.plasticscm.com/plasticrepo/plasticscm-mono-4.6.2/\
plasticscm-mono-4.6.2.tar.gz"
    _zips_format = \
        "{}/downloadinstaller/{{{{}}}}/plasticscm/linux/{{}}zip?Flags=None".format(Download)
    _client = _zips_format.format("client")
    _server = _zips_format.format("server")

    def get_client(version):
        return Uris._client.format(version)

    def get_server(version):
        return Uris._server.format(version)


class PlasticPaths:
    Base = "/opt/plasticscm5"
    Client = "{}/client".format(Base)
    Server = "{}/server".format(Base)
    Cm = "{}/cm".format(Client)

    class Tmp:
        Base = "{}/plasticupdater".format(tempfile.gettempdir())
        Server = "{}/server".format(Base)
        Client = "{}/client".format(Base)


def main():
    args = get_valid_args()

    if os.getuid() != 0:
        print(
            "This installer needs to be run with administrator privileges.",
            file=sys.stderr)
        return

    latest_version = retrieve_latest_version(args.labs)
    if latest_version is None:
        print("Unable to retrieve the latest version")
        return

    current_version = retrieve_current_version()
    is_already_installed = current_version is not None

    if is_already_installed and current_version == latest_version:
        print("Already up to date.")
        return

    if not is_already_installed:
        do_first_install(latest_version)
        return

    if not args.no_upgrade:
        do_upgrade(latest_version)


def get_valid_args():
    parser = argparse.ArgumentParser(
        description="Install or upgrade Plastic SCM from the ZIP bundles \
published in their website.")
    parser.add_argument(
        "--labs",
        action="store_true",
        help="Enable the latest releases from the Plastic SCM team.")
    parser.add_argument(
        "--no-upgrade",
        action="store_true",
        help="Prevents the installer from performing software upgrades.")
    return parser.parse_args()


def retrieve_latest_version(use_labs):
    try:
        with urlopen(Uris.Labs if use_labs else Uris.Download) as response:
            html = response.read().decode("utf-8")
    except Exception as e:
        print("Unable to open downloads page: {}".format(e), file=sys.stderr)
        traceback.print_stack(file=sys.stderr)
        return None

    return get_first_version(html)


def get_first_version(html):
    match = re.search("Version:.*\n *<span>([^ ]*)", html)
    return match.group(1) if match is not None else None


def retrieve_current_version():
    if not os.path.isdir(PlasticPaths.Base) or not os.path.exists(PlasticPaths.Cm):
        return None
    return subprocess.run(
        [PlasticPaths.Cm, "version"], stdout=subprocess.PIPE).stdout


def get_tmp_dir():
    if not os.path.isdir(PlasticPaths.Tmp.Base):
        os.makedirs(PlasticPaths.Tmp.Base)
    return PlasticPaths.Tmp.Base


def do_upgrade(version):
    pass  # TODO


def do_first_install(version):
    print("Installing Plastic SCM for the first time!")
    os.makedirs(PlasticPaths.Base, exist_ok=True)

    try:
        install_mono()
        install_client(version)
        install_server(version)
    except Exception as e:
        print("Installation failed: {}".format(e), file=sys.stderr)
        return

    print("All done!")


def install_mono():
    print("Downloading mono from '{}'...".format(Uris.Mono))
    try:
        with urlopen(Uris.Mono) as response:
            data = BytesIO(response.read())
            mono_gzip = gzip.GzipFile(fileobj=data, mode='rb')

            decompressed_data = BytesIO(mono_gzip.read())
            downloaded_tar = tarfile.TarFile(
                fileobj=decompressed_data, mode="r")

            downloaded_tar.extractall(PlasticPaths.Base)
    except Exception as e:
        shutil.rmtree(PlasticPaths.Mono, ignore_errors=True)
        raise


def install_client(latest_version):
    print("Installing client...")
    try:
        temp_dir = get_tmp_dir()
        download_zip_to_dir(Uris.get_client(latest_version), temp_dir)

        shutil.move(PlasticPaths.Tmp.Client, PlasticPaths.Client)
        # TODO the rest
    finally:
        shutil.rmtree(PlasticPaths.Tmp.Client, ignore_errors=True)


def install_server(latest_version):
    print("Installing server...")
    try:
        temp_dir = get_tmp_dir()
        download_zip_to_dir(Uris.get_server(latest_version), temp_dir)

        shutil.move(PlasticPaths.Tmp.Server, PlasticPaths.Server)
        # TODO the rest
    finally:
        shutil.rmtree(PlasticPaths.Tmp.Client, ignore_errors=True)


def download_zip_to_dir(uri, output_dir):
    print("Downloading '{}'...".format(uri))
    try:
        with urlopen(uri) as response:
            downloaded_zip = zipfile.ZipFile(BytesIO(response.read()))
            downloaded_zip.extractall(output_dir)
    except Exception as e:
        print("Unable to download from {}: {}".format(uri, e), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
