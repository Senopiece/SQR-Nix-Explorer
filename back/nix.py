from typing import List
import shutil
import os
import subprocess

import sqlite3


DEFAULT_STORES_ROOT = "/nix_stores/"
NIX_DB_PATH = "nix/var/nix/db/db.sqlite"


class Nix:
    command_append = [
        "--substituters",
        "/",
        "--option",
        "require-sigs",
        "false",
    ]

    def __init__(self, stores_root: str = DEFAULT_STORES_ROOT):
        self.stores_root = stores_root

        # Perhaps pin registry on init?
        # nix registry add nixpkgs github:NixOS/nixpkgs/nixos-21.05 --store /store
        # nix registry pin github:NixOS/nixpkgs/nixos-21.05 --store /store

        if not os.path.exists(self.stores_root):
            os.makedirs(self.stores_root)

    def _run_cmd(self, command: List[str], throw_on_fail: bool = True):
        command += self.command_append
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0 and throw_on_fail:
            error_message = stderr.decode().strip()
            raise Exception(f"Error during nix execution:\n{error_message}")

        return process.returncode, stdout, stderr

    def _assert_store_exists(self, store_name: str):
        directory_path = self._get_store_path(store_name)

        if not os.path.exists(directory_path):
            raise Exception(f"Store doesn't exist")

    def _get_store_paths(self, store_id: str):
        self._assert_store_exists(store_id)
        store_path = self._get_store_path(store_id)

        command = ["nix", "--store", store_path, "path-info", "--all"]
        _, stdout, _ = self._run_cmd(command)
        paths = stdout.decode().strip().split("\n")

        return paths

    def _get_package_closure(self, store_id: str, package):
        self._assert_store_exists(store_id)
        store_path = self._get_store_path(store_id)

        command = [
            "nix",
            "--store",
            store_path,
            "path-info",
            "--recursive",
            package,
        ]
        _, stdout, _ = self._run_cmd(command)
        paths = stdout.decode().strip().split("\n")

        return paths

    def _get_store_path(self, store_name: str) -> str:
        return os.path.abspath(os.path.join(self.stores_root, store_name))

    def get_ValidPaths(self, store_id: str):
        """
        Returns ValidPaths table from db.sqlite of a store
        """
        self._assert_store_exists(store_id)

        store_path = self._get_store_path(store_id)
        db_path = os.path.join(store_path, NIX_DB_PATH)

        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM ValidPaths")
        results = cursor.fetchall()

        return results

    def add_store(self, store_name: str) -> str:
        """
        Creates a new directory for a new store.
        Raises exception if store already exists.
        @returns: A path to created store (store ID).
        """

        directory_path = self._get_store_path(store_name)

        # Create store directory if it doesn't exist
        if os.path.exists(directory_path):
            raise Exception(
                f"Store named {store_name} already exists in the filetree."
            )
        os.makedirs(directory_path)

        # Pin registry ?
        # command = [
        #     "nix",
        #     "registry",
        #     "pin",
        #     "/path/to/registry.json",
        #     "--store",
        #     directory_path,
        # ]

        # self._run_cmd(command)

        return store_name

    def remove_store(self, store_id: str):
        """
        Expects sanitized input.
        Removes a store directory.
        """
        self._assert_store_exists(store_id)

        directory_path = self._get_store_path(store_id)

        # Check that the dir to be deleted in a folder we manage.
        # TODO: decide if keep this check.
        abs_root = os.path.abspath(self.stores_root)
        if os.path.commonpath([directory_path, abs_root]) != abs_root:
            raise Exception("Attempted to delete something outside stores dir")

        shutil.rmtree(directory_path)

    def add_package_to_store(self, store_id: str, package_name: str):
        """
        Adds (builds) a package to a store.
        """
        self._assert_store_exists(store_id)

        store_path = self._get_store_path(store_id)
        command = [
            "nix",
            "--store",
            store_path,
            "build",
            "--no-link",
            package_name,
        ]

        self._run_cmd(command)

    def remove_package_from_store(self, store_id: str, package_name: str):
        """
        Deletes a package recursively (closure of it's path).
        Throws an exception on nix error.
        """
        self._assert_store_exists(store_id)

        store_path = self._get_store_path(store_id)
        command = [
            "nix",
            "--store",
            store_path,
            "store",
            "delete",
            "--ignore-liveness",
            "--recursive",
            package_name,
        ]

        self._run_cmd(command)

    def check_package_exists(self, store_id: str, package_name: str) -> bool:
        """
        Checks if specified package exists in a store by invoking nix path-info.
        """
        self._assert_store_exists(store_id)

        store_path = self._get_store_path(store_id)
        command = ["nix", "--store", store_path, "path-info", package_name]
        ret, _, _ = self._run_cmd(command, throw_on_fail=False)
        if ret == 0:
            return True
        else:
            return False

    def get_package_closure_size(self, store_id: str, package: str) -> int:
        """
        Returns closure size in bytes invoking `nix path-info --closure-size`.
        """
        self._assert_store_exists(store_id)

        store_path = self._get_store_path(store_id)

        command = [
            "nix",
            "--store",
            store_path,
            "path-info",
            "--closure-size",
            package,
        ]
        _, stdout, _ = self._run_cmd(command)

        size = stdout.decode().strip().split("\t")[1]
        return int(size)

    def get_difference_of_paths(
        self, store_id1: str, store_id2: str
    ) -> List[str]:
        """
        Returns a list of paths that are in first store but not in second.
        Throws an exception on nix error.
        """
        self._assert_store_exists(store_id1)
        self._assert_store_exists(store_id2)

        paths1 = self._get_store_paths(store_id1)
        paths2 = self._get_store_paths(store_id2)

        return list(set(paths1) - set(paths2))

    def get_difference_of_package_closures(
        self, store_id1: str, package1: str, store_id2: str, package2: str
    ) -> List[str]:
        """
        Returns a list of paths that are in first package but not in second.
        Throws an exception on nix error.
        """
        self._assert_store_exists(store_id1)
        self._assert_store_exists(store_id2)

        paths1 = self._get_package_closure(store_id1, package1)
        paths2 = self._get_package_closure(store_id2, package2)

        return list(set(paths1) - set(paths2))
