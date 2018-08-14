#!/usr/bin/env python
""" Release code for the nf-core python package.

Bumps the version number in all appropriate files for
a nf-core pipeline
"""

import cookiecutter.main, cookiecutter.exceptions
import git
import logging
import os
import re
import shutil
import sys
import tempfile

import nf_core

class PipelineCreate(object):
    """ Object to create a new pipeline """

    def __init__(self, name, description, new_version='1.0dev', no_git=False, force=False, outdir=None):
        """ Init the object and define variables """
        self.name = name
        self.description = description
        self.new_version = new_version
        self.no_git = no_git
        self.force = force
        self.outdir = outdir
        if not self.outdir:
            self.outdir = os.path.join(os.getcwd(), self.name)

    def init_pipeline(self):
        """Function to init a new pipeline. Called by the main cli"""

        # Make the new pipeline
        self.run_cookiecutter()

        # Init the git repository and make the first commit
        if not self.no_git:
            self.git_init_pipeline()

    def run_cookiecutter(self):
        """Run cookiecutter to create a new pipeline"""

        logging.info("Creating new nf-core pipeline: {}".format(self.name))

        # Check if the output directory exists
        if os.path.exists(self.outdir):
            if self.force:
                logging.warn("Output directory '{}' exists - continuing as --force specified".format(self.outdir))
            else:
                logging.error("Output directory '{}' exists!".format(self.outdir))
                logging.info("Use -f / --force to overwrite existing files")
                sys.exit(1)
        else:
            os.makedirs(self.outdir)

        # Build the template in a temporary directory
        tmpdir = tempfile.mkdtemp()
        template = os.path.join(os.path.dirname(os.path.realpath(nf_core.__file__)), 'pipeline-template/')
        cookiecutter.main.cookiecutter (
            template,
            extra_context={'pipeline_name':self.name, 'pipeline_short_description':self.description, 'version':self.new_version},
            no_input=True,
            overwrite_if_exists=self.force,
            output_dir=tmpdir
        )

        # Move the template to the output directory
        for f in os.listdir(os.path.join(tmpdir, self.name)):
            shutil.move(os.path.join(tmpdir, self.name, f), self.outdir)

        # Delete the temporary directory
        shutil.rmtree(tmpdir)


    def git_init_pipeline(self):
        """Initialise the new pipeline as a git repo and make first commit"""
        logging.info("Initialising pipeline git repository")
        repo = git.Repo.init(self.outdir)
        repo.git.add(A=True)
        repo.index.commit("initial template build from nf-core/tools, version {}".format(nf_core.__version__))
        logging.info("Done. Remember to add a remote and push to GitHub:\n  cd {}\n  git remote add origin git@github.com:USERNAME/REPO_NAME.git\n  git push".format(self.outdir))
