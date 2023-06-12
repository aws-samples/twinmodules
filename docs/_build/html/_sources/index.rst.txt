.. twinmodules documentation master file, created by
   sphinx-quickstart on Tue May 30 08:36:01 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to twinmodules's documentation!
=======================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   
	modules
	twinmodules
	
Indices and tables
==================

Browse the API:

* :ref:`modindex`

Or search for something specific:

* :ref:`search`


TwinModules
==================

The goal of TwinModules is to provide a python API that reduces the time spent coding routine functions needed to interact with the AWS cloud or local data sources.  TwinModules currently does not intend to provide Infrastructure as Code (IaC) automation. 

Supported functionality includes, but is not limited to:
- Building docker images and pushing to AWS ECR
- Tools for push and pulling data from:
  - AWS S3 Buckets
  - AWS IoT SiteWise
  - AWS SQS
  - AWS Timestream
  - AWS RDS
- Tools for HPC style job execution utilizing AWS Batch
- Automation (Intended to be used in conjunction with TwinStat):
  - Autoscaling virtual sensors
    - detect when virtual sensors need to be created or destroyed
  - Timeseries signal statistical steady-state detection
  - Set up of SQL backends for:
   - uncertainty propagation
   - sensitivity studies
   - global optimization
    

Requirements: 
==================

- Supported Operating Systems: Linux, Windows
- Python 3.10+

Installation
==================

Users can either clone this repo and import in a dev environment, or use a python wheel in the /dist folders.

.. code-block:: python

	git clone git@ssh.gitlab.aws.dev:autonomouscomputesateam/twinmodules.git
	cd twinmodules/dist
	pip install ./*.whl



API Documentation
==================

Auto-documentation can be found here:

https://gitlab.aws.dev/autonomouscomputesateam/twinmodules/-/tree/main/docs/_build/html

Users can:

.. code-block:: python

	git clone git@ssh.gitlab.aws.dev:autonomouscomputesateam/twinmodules.git
	cd twinmodules/docs/_build/html

View the index.html to review API documentation.

Full tutorials to be published on AWS Samples in Q4 2023.


License
==================

This repository is released under the MIT-0 License. See the LICENSE file for details.




