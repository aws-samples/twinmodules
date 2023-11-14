# TwinModules

The goal of TwinModules is to provide a python API that reduces the time spent coding routine functions needed to interact with the AWS cloud or local data sources.  TwinModules currently does not intend to provide Infrastructure as Code (IaC) automation. 

TwinModules is part of the [TwinFlow](https://github.com/aws-samples/twinflow) toolset which can be read about in this [blog](https://aws.amazon.com/blogs/hpc/predictive-models-and-simulations-with-twinflow-on-aws/). Other tools within TwinFlow are [TwinStat](https://github.com/aws-samples/twinstat), which provides a few data science tools needed for Level 4 digital twins, and [TwinGraph](https://github.com/aws-samples/twingraph), which enables scalable graph orchestration.


Supported functionality includes, but will not be limited to:
- Building docker images and pushing to AWS ECR
- Tools for push and pulling data from:
  - AWS S3 Buckets
  - AWS IoT SiteWise
  - AWS SQS
  - AWS Timestream
  - AWS RDS
  - AWS CloudFormation metadata
- Tools for HPC style job execution utilizing AWS Batch
- Automation (Intended to be used in conjunction with TwinStat):
  - Autoscaling virtual sensors
    - detect when virtual sensors need to be created or destroyed
  - Timeseries signal statistical steady-state detection
  - Set up of SQL backends for:
   - uncertainty propagation
   - sensitivity studies
   - global optimization
    

### Requirements: 

- Supported Operating Systems: Linux, Windows
- Python 3.10+

## Installation

Users can either clone this repo and import in a dev environment, or use a python wheel in the /dist folders.

```
git clone git@ssh.gitlab.aws.dev:autonomouscomputesateam/twinmodules.git
cd twinmodules/dist
pip install ./*.whl

```


## API Documentation

Auto-documentation can be found here:

Users can:

```
git clone git@github.com:aws-samples/twinmodules.git
cd twinmodules/docs/_build/html
```
View the index.html to review API documentation.

Full tutorials to be published on AWS Samples in Q4 2023.


## License
This repository is released under the MIT-0 License. See the LICENSE file for details.

## Credits

This open source framework was developed by the Autonomous Computing Team within Amazon Web Services (AWS) Worldwide Specialist Organization (WWSO). Developers include Ross Pivovar, Satheesh Maheswaran, Vidyasagar Ananthan, and Cheryl Abundo. Authors would like to thank Alex Iankoulski for his detailed guidance and expertise in reviewing the code.
