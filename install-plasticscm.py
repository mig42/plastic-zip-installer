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


BASE = "/opt/plasticscm5"


class Paths:
    CertsFile = "/etc/ssl/certs/ca-certificates.crt"
    Base = "/opt/plasticscm5"

    class Mono:
        _bin = "{}/mono/bin".format(BASE)
        _certtools = "{}/certtools".format(BASE)
        CertSync = "{}/cert-sync".format(_bin)
        CertMgr = "{}/certmgr".format(_certtools)
        Mozroots = "{}/mozroots".format(_certtools)

    class Plastic:
        Client = "{}/client".format(BASE)
        Server = "{}/server".format(BASE)
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
    if not os.path.isdir(BASE) or not os.path.exists(Paths.Plastic.Cm):
        return None
    return subprocess.run(
        [Paths.Plastic.Cm, "version"], stdout=subprocess.PIPE).stdout


def get_tmp_dir():
    if not os.path.isdir(Paths.Tmp.Base):
        os.makedirs(Paths.Tmp.Base)
    return Paths.Tmp.Base


def do_upgrade(version):
    print("Upgrading Plastic SCM to version {}".format(version))
    # TODOS


def do_first_install(version):
    print("Installing Plastic SCM for the first time!")
    print("Version: {}".format(version))

    os.makedirs(BASE, exist_ok=True)
    try:
        install_mono()
        install_client(version)
        install_server(version)
    except Exception as e:
        print("Installation failed: {}".format(e), file=sys.stderr)
        return

    print("All done!")


def install_mono():
    download_mono()
    update_certificates()


def download_mono():
    print("Downloading mono from '{}'...".format(Uris.Mono))
    try:
        with urlopen(Uris.Mono) as response:
            data = BytesIO(response.read())
            mono_gzip = gzip.GzipFile(fileobj=data, mode='rb')

            decompressed_data = BytesIO(mono_gzip.read())
            downloaded_tar = tarfile.TarFile(
                fileobj=decompressed_data, mode="r")

            downloaded_tar.extractall(BASE)
    except Exception as e:
        shutil.rmtree(Paths.Plastic.Mono, ignore_errors=True)
        raise


def update_certificates():
    run_certificates_command()
    if os.path.isfile(Paths.CertsFile):
        subprocess.run([Paths.Mono.CertSync, Paths.CertsFile])

    run_command(
        Paths.Mono.CertMgr,
        ["-ssl", "-m", "-y", "https://www.plasticscm.com/"])
    run_command(
        Paths.Mono.CertMgr,
        ["-ssl", "-m", "-y", "https://cloud.plasticscm.com/"])

    run_command(
        Paths.Mono.Mozroots, ["--import", "--machine", "--add-only"])


def run_certificates_command():
    certs_command, args = get_certificates_command()
    if certs_command is None:
        print("Unable to update certificates", file=sys.stderr)
        return

    run_command(certs_command, args)


def run_command(name, args):
    print("Executing '{} {}'".format(name, args))
    if subprocess.run([name] + args).returncode != 0:
        print("Failed!", file=sys.stderr)


def get_certificates_command():
    if is_command_in_path("update-ca-certificates"):
        return "update-ca-certificates", []

    if is_command_in_path("trust"):
        return "trust", ["extract-compat"]

    return None


def is_command_in_path(command):
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')

        exe_file = os.path.join(path, command)
        if is_exe(exe_file):
            return exe_file

    return None


def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def install_client(latest_version):
    print("Installing client...")
    try:
        temp_dir = get_tmp_dir()
        download_zip_to_dir(Uris.get_client(latest_version), temp_dir)

        shutil.move(Paths.Tmp.Client, Paths.Plastic.Client)
        # TODO the rest
    finally:
        shutil.rmtree(Paths.Tmp.Client, ignore_errors=True)


def install_server(latest_version):
    print("Installing server...")
    try:
        temp_dir = get_tmp_dir()
        download_zip_to_dir(Uris.get_server(latest_version), temp_dir)

        shutil.move(Paths.Tmp.Server, Paths.Plastic.Server)
        # TODO the rest
    finally:
        shutil.rmtree(Paths.Tmp.Client, ignore_errors=True)


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
