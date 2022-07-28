import json
import os
import tempfile
from pathlib import Path

import pytest

import nf_core.modules
import nf_core.modules.modules_command

from ..utils import GITLAB_URL

"""
Test the 'nf-core modules patch' command

Uses a branch (patch-tester) in the GitLab nf-core/modules-test repo when
testing if the update commands works correctly with patch files
"""

ORG_SHA = "22c7c12dc21e2f633c00862c1291ceda0a3b7066"
SUCCEED_SHA = "f7d3a3894f67db2e2f3f8c9ba76f8e33356be8e0"
FAIL_SHA = "b4596169055700533865cefb7542108418f53100"
MODULE = "bismark/align"
REPO_NAME = "nf-core/modules-test"
PATCH_BRANCH = "patch-tester"


def setup_patch(pipeline_dir, modify_module):
    install_obj = nf_core.modules.ModuleInstall(
        pipeline_dir, prompt=False, force=True, remote_url=GITLAB_URL, branch=PATCH_BRANCH, sha=ORG_SHA, no_pull=True
    )

    # Install the module
    install_obj.install(MODULE)

    if modify_module:
        # Modify the module
        module_path = Path(pipeline_dir, "modules", REPO_NAME, MODULE)
        modify_main_nf(module_path / "main.nf")


def modify_main_nf(path):
    """Modify a file to test patch creation"""
    with open(path, "r") as fh:
        lines = fh.readlines()
    # We want a patch file that looks something like:
    # -    tuple val(meta), path(reads)
    # -    path index
    # +    tuple val(meta), path(reads), path(index)
    lines[10] = "    tuple val(meta), path(reads), path(index)\n"
    lines.pop(11)
    with open(path, "w") as fh:
        fh.writelines(lines)


def test_create_patch_no_change(self):
    """Test creating a patch when there is no change to the module"""
    setup_patch(self.pipeline_dir, False)

    # Try creating a patch file
    patch_obj = nf_core.modules.ModulePatch(self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True)
    with pytest.raises(UserWarning):
        patch_obj.patch(MODULE)

    module_path = Path(self.pipeline_dir, "modules", REPO_NAME, MODULE)

    # Check that no patch file has been added to the directory
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml"}

    # Check the 'modules.json' contains no patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) is None


def test_create_patch_change(self):
    """Test creating a patch when there is a change to the module"""
    setup_patch(self.pipeline_dir, True)

    # Try creating a patch file
    patch_obj = nf_core.modules.ModulePatch(self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True)
    patch_obj.patch(MODULE)

    module_path = Path(self.pipeline_dir, "modules", REPO_NAME, MODULE)

    patch_fn = f"{'-'.join(MODULE.split('/'))}.diff"
    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path("modules", REPO_NAME, MODULE, patch_fn)

    # Check that the correct lines are in the patch file
    with open(module_path / patch_fn, "r") as fh:
        patch_lines = fh.readlines()
    module_relpath = module_path.relative_to(self.pipeline_dir)
    assert f"--- {module_relpath / 'main.nf'}\n" in patch_lines, module_relpath / "main.nf"
    assert f"+++ {module_relpath / 'main.nf'}\n" in patch_lines
    assert "-    tuple val(meta), path(reads)\n" in patch_lines
    assert "-    path index\n" in patch_lines
    assert "+    tuple val(meta), path(reads), path(index)\n" in patch_lines


def test_create_patch_try_apply_successful(self):
    """
    Test creating a patch file and applying it to a new version of the the files
    """
    setup_patch(self.pipeline_dir, True)
    module_relpath = Path("modules", REPO_NAME, MODULE)
    module_path = Path(self.pipeline_dir, module_relpath)

    # Try creating a patch file
    patch_obj = nf_core.modules.ModulePatch(self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True)
    patch_obj.patch(MODULE)

    patch_fn = f"{'-'.join(MODULE.split('/'))}.diff"
    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path("modules", REPO_NAME, MODULE, patch_fn)

    update_obj = nf_core.modules.ModuleUpdate(
        self.pipeline_dir, sha=SUCCEED_SHA, remote_url=GITLAB_URL, branch=PATCH_BRANCH
    )
    # Install the new files
    install_dir = Path(tempfile.mkdtemp())
    update_obj.install_module_files(MODULE, SUCCEED_SHA, update_obj.modules_repo, install_dir)

    # Try applying the patch
    module_install_dir = install_dir / MODULE
    patch_relpath = module_relpath / patch_fn
    assert update_obj.try_apply_patch(MODULE, REPO_NAME, patch_relpath, module_path, module_install_dir) is True

    # Move the files from the temporary directory
    update_obj.move_files_from_tmp_dir(MODULE, module_path, install_dir, REPO_NAME, SUCCEED_SHA)

    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path("modules", REPO_NAME, MODULE, patch_fn)

    # Check that the correct lines are in the patch file
    with open(module_path / patch_fn, "r") as fh:
        patch_lines = fh.readlines()
    module_relpath = module_path.relative_to(self.pipeline_dir)
    assert f"--- {module_relpath / 'main.nf'}\n" in patch_lines
    assert f"+++ {module_relpath / 'main.nf'}\n" in patch_lines
    assert "-    tuple val(meta), path(reads)\n" in patch_lines
    assert "-    path index\n" in patch_lines
    assert "+    tuple val(meta), path(reads), path(index)\n" in patch_lines


def test_create_patch_try_apply_failed(self):
    """
    Test creating a patch file and applying it to a new version of the the files
    """
    setup_patch(self.pipeline_dir, True)
    module_relpath = Path("modules", REPO_NAME, MODULE)
    module_path = Path(self.pipeline_dir, module_relpath)

    # Try creating a patch file
    patch_obj = nf_core.modules.ModulePatch(self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True)
    patch_obj.patch(MODULE)

    patch_fn = f"{'-'.join(MODULE.split('/'))}.diff"
    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path("modules", REPO_NAME, MODULE, patch_fn)

    update_obj = nf_core.modules.ModuleUpdate(
        self.pipeline_dir, sha=FAIL_SHA, remote_url=GITLAB_URL, branch=PATCH_BRANCH
    )
    # Install the new files
    install_dir = Path(tempfile.mkdtemp())
    update_obj.install_module_files(MODULE, FAIL_SHA, update_obj.modules_repo, install_dir)

    # Try applying the patch
    module_install_dir = install_dir / MODULE
    patch_path = module_relpath / patch_fn
    assert update_obj.try_apply_patch(MODULE, REPO_NAME, patch_path, module_path, module_install_dir) is False


def test_create_patch_update_success(self):
    """
    Test creating a patch file and the updating the module

    Should have the same effect as 'test_create_patch_try_apply_successful'
    but uses higher level api
    """
    setup_patch(self.pipeline_dir, True)
    module_path = Path(self.pipeline_dir, "modules", REPO_NAME, MODULE)

    # Try creating a patch file
    patch_obj = nf_core.modules.ModulePatch(self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True)
    patch_obj.patch(MODULE)

    patch_fn = f"{'-'.join(MODULE.split('/'))}.diff"
    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path("modules", REPO_NAME, MODULE, patch_fn)

    # Update the module
    update_obj = nf_core.modules.ModuleUpdate(
        self.pipeline_dir, sha=SUCCEED_SHA, show_diff=False, remote_url=GITLAB_URL, branch=PATCH_BRANCH
    )
    update_obj.update(MODULE)

    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    with open(Path(self.pipeline_dir, "modules.json"), "r") as fh:
        print("Real file", self.pipeline_dir)
        print(fh.read())
    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path(
        "modules", REPO_NAME, MODULE, patch_fn
    ), modules_json_obj.get_patch_fn(MODULE, REPO_NAME)

    # Check that the correct lines are in the patch file
    with open(module_path / patch_fn, "r") as fh:
        patch_lines = fh.readlines()
    module_relpath = module_path.relative_to(self.pipeline_dir)
    assert f"--- {module_relpath / 'main.nf'}\n" in patch_lines
    assert f"+++ {module_relpath / 'main.nf'}\n" in patch_lines
    assert "-    tuple val(meta), path(reads)\n" in patch_lines
    assert "-    path index\n" in patch_lines
    assert "+    tuple val(meta), path(reads), path(index)\n" in patch_lines


def test_create_patch_update_fail(self):
    """
    Test creating a patch file and updating a module when there is a diff conflict
    """
    setup_patch(self.pipeline_dir, True)
    module_path = Path(self.pipeline_dir, "modules", REPO_NAME, MODULE)

    # Try creating a patch file
    patch_obj = nf_core.modules.ModulePatch(self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True)
    patch_obj.patch(MODULE)

    patch_fn = f"{'-'.join(MODULE.split('/'))}.diff"
    # Check that a patch file with the correct name has been created
    assert set(os.listdir(module_path)) == {"main.nf", "meta.yml", patch_fn}

    # Check the 'modules.json' contains a patch file for the module
    modules_json_obj = nf_core.modules.modules_json.ModulesJson(self.pipeline_dir)
    assert modules_json_obj.get_patch_fn(MODULE, REPO_NAME) == Path("modules", REPO_NAME, MODULE, patch_fn)

    # Save the file contents for downstream comparison
    with open(module_path / patch_fn, "r") as fh:
        patch_contents = fh.read()

    update_obj = nf_core.modules.ModuleUpdate(
        self.pipeline_dir, sha=FAIL_SHA, show_diff=False, remote_url=GITLAB_URL, branch=PATCH_BRANCH
    )
    update_obj.update(MODULE)

    # Check that the installed files have not been affected by the attempted patch
    temp_dir = Path(tempfile.mkdtemp())
    nf_core.modules.modules_command.ModuleCommand(
        self.pipeline_dir, GITLAB_URL, PATCH_BRANCH, no_pull=True
    ).install_module_files(MODULE, FAIL_SHA, update_obj.modules_repo, temp_dir)

    temp_module_dir = temp_dir / MODULE
    for file in os.listdir(temp_module_dir):
        assert file in os.listdir(module_path)
        with open(module_path / file, "r") as fh:
            installed = fh.read()
        with open(temp_dir / file, "r") as fh:
            shouldbe = fh.read()
        assert installed == shouldbe

    # Check that the patch file is unaffected
    with open(module_path / patch_fn, "r") as fh:
        new_patch_contents = fh.read()
    assert patch_contents == new_patch_contents
