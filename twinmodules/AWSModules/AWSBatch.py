# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

#%%
import boto3
import time
from twinmodules.core.util import exponential_backoff

class batch(object):
    '''

    Handle both the IaC for AWS Batch and
    utilization of queues, job submission, etc.

    The IaC is relying on AWS SDK, in the future it will
    be swapped for CDK.

    The SDK portion utilizies exponential backoff for submission
    of large number of jobs or waits.

    Parameters
    ----------
    infrastructure_type : str
        Determines underlying infrastructure type.
        e.g. EKS, Fargate, EC2

    '''

    def __init__(self,  infrastructure_type:str,
                        region:str = "us-east-1",
                        batch_namespace:str = "batch-namespace",  #underscore not allowed
                        queue_name:str="my-queue-1",
                        computeEnvironmentName:str='TwinFlow_batch_env',
                        minvCpus: int = 1,
                        maxvCpus: int = 500,
                        instanceTypes:str='optimal',
                        IAM_role:str=None
                        ):
        '''


        Parameters
        ----------
        infrastructure_type : str
            Options are: 'ec2', 'eks','fargate'
        region : str, optional
            The default is "us-east-1".
        batch_namespace : str, optional
            The default is "batch-namespace".
        queue_name : str, optional
            The default is "my-queue-1".
        computeEnvironmentName : str, optional
            The default is 'TwinFlow_batch_env'.
        minvCpus : int, optional
            Any value greater than or equal to zero.  A value of zero means the
            cluster will auto close all compute instances when finished, but requires the
            longest start up time for new jobs.  If a user selects a warm startup configuration
            such as a value of 500, a cluster will remain provisioned and provide the fastest
            startup time for new jobs, but also includes costs of keeping these instances open.
            The default is 1.
        maxvCpus : int, optional
            Prevent AWS Batch from using more than this many cpus.
            The default is 500.
        instanceTypes : str, optional
            Specify the exact instant type or leave this as default for Batch auto selection.
            When defining batch jobs with 'defineBatchJob', users can select a GPU instance. However,
            if a user wants a specific type, such as a P4, that must be defined here.
            The default is 'optimal'.
        IAM_role : str, optional
            What is the IAM role that the compute instances will assume.
            The default is None.


        Returns
        -------
        None.

        '''

        self.infrastructure_type = infrastructure_type
        self.region = region
        self.batch_namespace = batch_namespace
        self.queue_name = queue_name
        self.computeEnvironmentName = computeEnvironmentName
        self.minvCpus = minvCpus
        self.maxvCpus = maxvCpus
        self.instanceTypes = instanceTypes

        self.IAM_role = IAM_role

        accepted_options = ['ec2', 'eks','fargate']
        if self.infrastructure_type.lower() not in accepted_options:
            raise ValueError("ERROR: Batch infrastructure option " \
                             +"must be one of: {}".format(', '.join(accepted_options)))

        if (self.infrastructure_type.lower() == 'ec2' or self.infrastructure_type.lower() == 'fargate') \
            and IAM_role is None:
            raise ValueError("ERROR: an IAM role must be specified with execution permission"
                             +" when using an ec2/fargate infrastructure.")

        self.batch_client = boto3.client('batch',region_name = self.region )

    @exponential_backoff()
    def sendBatchJob(self, jobName:str,
                           jobDefinitionName:str,
                           override_command:list=None,
                           override_resource:dict={}
                           ) -> None:
        '''

        Parameters
        ----------
        jobName : str
            The name for this specific job submission.
        jobDefinitionName : str
            The name of the job definition to use.
        override_command : list, optional
            When running this job, what command line argument should be used
            instead of the command provided in the job definition.
            The default is None.
        override_resource : list, optional
            When running this job, what resources should be used
            instead of the resources provided in the job definition.
            The default is None.

        Returns
        -------

            .. code-block:: python

                print(response)
                {
                'jobId': '876da822-4198-45f2-a252-6cea32512ea8',
                'jobName': 'example',
                'ResponseMetadata': {
                    '...': '...',
                    },
                }
        '''

        if override_command is not None:
            #the automation only wants strings
            override_command = list(map(str, override_command))

        # if override_resource is not None:
        #     if isinstance(override_resource,dict):
        #         override_resource = {key:str(value) for key,value in override_resource.items()}

        containerOverrides = {  "command":override_command }
        if 'cpu' in override_resource.keys():
            containerOverrides['vcpus'] = override_resource.get('cpu',None)
        if 'Mem' in override_resource.keys():
            containerOverrides['memory'] = override_resource.get('Mem',None)


        response = self.batch_client.submit_job(
                                           jobName=jobName,
                                           jobDefinition=jobDefinitionName,
                                           jobQueue =self.queue_name,
                                           containerOverrides =containerOverrides
                                           # {
                                           #     "command":override_command,
                                           #     #TODO: enable resource override
                                           #     #"resourceRequirements": override_resource
                                           #     'vcpus' : override_resource.get('cpu',{}),
                                           #     'memory' : override_resource.get('Mem',{})
                                           #     }
                                           )

        return response


    def removeJobDefinition(self, jobDefinitionName:str) -> None:
        '''
        This will delete all versions of the job definition.

        Parameters
        ----------
        jobDefinitionName : str

        Returns
        -------
        None.

        '''

        #boto will not return all job def if there are massive
        #numbers e.g. 1000+
        while True:
            job_defs = self.batch_client.describe_job_definitions(
                                                                  status='ACTIVE',
                                                                  jobDefinitionName=jobDefinitionName)
            all_defs = job_defs['jobDefinitions']

            if len(all_defs) == 0:
                break

            for definition in all_defs:
                try:
                    self.batch_client.deregister_job_definition(jobDefinition=
                          definition['jobDefinitionName'] + ":" + str(definition['revision']))
                except Exception as e:
                    if "Too Many Requests" in str(e):
                        time.sleep(1)
                    else:
                        raise e



    def _iam_convert_profile_role(self, IAM_type):
        '''
        Helper function to convert roles and profiles depends on the location
        in the setup files.

        'arn:aws:iam::<account number>:role/TwinFlow-instance-role'
        'arn:aws:iam::<account number>:instance-profile/TwinFlow-instance-role'
        '''

        if IAM_type == 'role':
            new = self.IAM_role.replace(':instance-profile', ':role' )
        else:
            new = self.IAM_role.replace(':role', ':instance-profile')

        return new

    #TODO: need to setup persistent filestore with batch (lustre is main desire)
    def defineBatchJob(self, image_name_uri: str,
                             host_path:str,
                             job_command: list,
                             cpu: int,
                             memory: int,
                             jobDefinitionName: str,
                             gpu:int=0,
                             timeout:int=0,
                             environ_vars:dict=None) -> None:
        '''
        Create an AWS Batch job definition that can be utilized
        by any number of jobs.

        Parameters
        ----------
        image_name_uri : str
            The container end point reference such as ECR location.
        host_path : str
            If using EKS, host path must be defined.
        job_command : list
            Default command line arguments, can be overridden for
            each job submission.
        cpu : int
            How many vcpu are required.
        memory : int
            How much RAM in MB is required.
        jobDefinitionName : str
            Name the definition
        gpu : int, optional
            How many GPUs are needed. The default is 0.
        timeout : int, optional
            Job will be auto-aborted after this amount of time (sec). The default is 0.
        environ_vars : dict, optional
            What environmental variables should be set prior to
            job command execution. The default is None.

        Returns
        -------
        None

        '''

        #the automation only wants strings
        job_command = list(map(str, job_command))

        #setup the environment variable inputs if provided by user
        env = []
        if environ_vars is not None:
            for key,value in environ_vars.items():
                env.append(
                {
                    "name": key,
                    "value":value
                 }
                )


        job_config = {}
        job_config["jobDefinitionName"] = jobDefinitionName
        job_config["type"] = "container"
        if timeout > 0:
            job_config["timeout"] = {"attemptDurationSeconds": timeout}


        if self.infrastructure_type.lower() == 'ec2' \
            or self.infrastructure_type.lower() == 'fargate':

              job_config["containerProperties"] = \
              {
                "command":job_command,
                "image": image_name_uri,
                "resourceRequirements": [
                  {
                    "type": "VCPU",
                    "value": str(cpu)
                  },
                  {
                    "type": "MEMORY",
                    "value": str(memory)
                  }
                ],
                "executionRoleArn": self._iam_convert_profile_role('role'),
                "jobRoleArn": self._iam_convert_profile_role('role'),
                "environment": env,
                #TODO: come back to this later (persistent file storage)
                # "linuxParameters": {
                #   "tmpfs": [],
                #   "devices": []
                # },
                # "mountPoints": [],
                "logConfiguration": {
                  "logDriver": "awslogs"
                }
              }

              if self.infrastructure_type.lower() == 'fargate':
                  job_config["containerProperties"]["fargatePlatformConfiguration"] = \
                                                      {
                                                          "platformVersion": "LATEST"
                                                      }
                  job_config["containerProperties"]["networkConfiguration"] = \
                                                      {
                                                            "assignPublicIp": "ENABLED"
                                                      }


              job_config["platformCapabilities"] = [self.infrastructure_type.upper()]

              #fargate currently doesnt support gpu
              if gpu > 0 and self.infrastructure_type.lower() == 'ec2':
                  job_config["containerProperties"]["resourceRequirements"] \
                      .append(
                              {
                                  "type": "GPU",
                                  "value": str(gpu)
                              }
                          )

        else:

            job_config["eksProperties"] = \
            {
                "podProperties": {
                    "hostNetwork":True,
                    "containers":
                        [
                            {
                                "image": image_name_uri,
                                "command": job_command,
                                "resources": {
                                        "limits": {
                                                "cpu":str(cpu),
                                                "memory":str(memory) + "Mi"
                                                }
                                            },
                                "volumeMounts": [
                                    {
                                        "mountPath":"/wd",
                                        "name": "pod-mount",
                                        "readOnly": False
                                        }
                                    ],
                                "env": env,
                             }
                        ],
                        "volumes":
                            [
                                {
                                "name":"pod-mount",
                                "hostPath":
                                    {
                                      "path":host_path
                                    }
                                }
                            ]
                    }
                }

        self.batch_client.register_job_definition(**job_config)


    def generateBatch(self, **kwargs):
        '''

        Deprecated: Use CDK

        Generate the AWS Batch environment and the queue needed to
        run jobs in AWS Batch.

        Parameters
        ----------
        Most setup should be set during object instantiation and
        thus a user only needs to call this method to generate the batch.

        Returns
        -------
        None.

        '''
        if self.infrastructure_type.lower() == 'ec2':
            self._generateBatch_ec2_fargate("EC2", **kwargs)
        elif self.infrastructure_type.lower() == 'fargate':
            self._generateBatch_ec2_fargate("FARGATE", **kwargs)
        elif self.infrastructure_type.lower() == 'eks':
            print("WARNING: an EKS cluster will not be auto-generated"
                  +" please use EKS blueprints or AWS Console."
                  +" If the EKS cluster already exists, a queue"
                  +" will be created.")
            self._generateBatch_eks(**kwargs)
        else:
            raise ValueError("ERROR: Unknown compute type.")



    def _generateBatch_ec2_fargate(self, compute_type:str,
                                        vpc_id:str=None,
                                        sg_group:str=None,
                                        specific_subnets:list=None) -> None:

        #apparently boto3 doesnt yet support grabbing ONLY the current ec2 info.  Right now
        #it grabs all or nothing. So use the http metadata instead
        #https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-categories.html
        import urllib.request
        mac = urllib.request.urlopen('http://169.254.169.254/latest/meta-data/mac').read().decode()

        #create compute environment -------------------------------------------------------
        ec2_client = boto3.client('ec2', region_name = self.region )

        if vpc_id is None:
            vpc_id = urllib.request.urlopen('http://169.254.169.254/latest/meta-data/network/interfaces/macs/{}/vpc-id'\
                                                .format(mac)).read().decode()

        if sg_group is None:
            sg = urllib.request.urlopen(                                                             \
                'http://169.254.169.254/latest/meta-data/network/interfaces/macs/{}/security-group-ids' \
                                                .format(mac)).read().decode().split('\n')
        else:
            if vpc_id is None:
                raise ValueError("ERROR: if security group provided, user must also provide VPC id.")

        #get a list of all the subnets in this VPC
        ec2_config = ec2_client.describe_subnets(
                                                  Filters=[{
                                                    'Name': 'vpc-id',
                                                    'Values':[vpc_id]
                                                   }] )
        if specific_subnets is None:
            #TODO: sometimes there are tags that describe the subnet, not sure why these disappear depending
            #on ec2 type
            if 'Tags' in ec2_config['Subnets'][0].keys():
                subnets = [x['SubnetId'] for x in ec2_config['Subnets'] if 'public' in x['Tags'][0]['Value']]
            else:
                subnets = [x['SubnetId'] for x in ec2_config['Subnets'] ]
        else:
            subnets = specific_subnets

        #create an AWS compute environment
        batch_config = {}
        batch_config["computeEnvironmentName"] = self.computeEnvironmentName
        batch_config["type"] = "MANAGED"
        batch_config["state"] = "ENABLED"
        batch_config["computeResources"] = \
           {
            "type": compute_type,
            "maxvCpus": self.maxvCpus,
            "subnets": subnets,
            "securityGroupIds": sg
          }

        if compute_type.lower() == 'ec2':
            batch_config["computeResources"]["allocationStrategy"] = "BEST_FIT_PROGRESSIVE"
            batch_config["computeResources"]["desiredvCpus"] = self.minvCpus +1
            batch_config["computeResources"]["instanceRole"] = self._iam_convert_profile_role('profile')
            batch_config["computeResources"]["instanceTypes"] = [self.instanceTypes]
            batch_config["computeResources"]["minvCpus"] = self.minvCpus


        try:
            self.batch_client.create_compute_environment(**batch_config)
        except Exception as e:
            if "already exists" in str(e):
                print("Compute environment already exists.")
            else:
                raise e

        self._generateQueue()




    def _generateBatch_eks(self, eks_cluster_name:str = "mykubeflow",
                          specific_subnets:list=None ) -> None:

        # for security best practices, all of this code was removed
        # in favor of EKS-blueprints

        #get eks config -------------------------------------------------------------------

        #create compute environment -------------------------------------------------------
        batch_client = boto3.client('batch')

        #create the batch queue -------------------------------------------------------------------
        self._generateQueue(batch_client)


    def _run_k8_configuration(self, batch_namespace):
        ''' Note that all of these are copy and pastes from
            the AWS Batch how-to setup.  The shell scripts or
            yaml have been converted to API calls by using the
            kubernetes python API.

            https://docs.aws.amazon.com/batch/latest/userguide/getting-started-eks.html

            Kubernetes API:

            https://github.com/kubernetes-client/python/blob/master/examples/apply_from_dict.py
        '''

        from kubernetes import client, config, utils
        from kubernetes.utils import FailToCreateError

        config.load_kube_config()
        k8s_client = client.ApiClient()


        #namespace setup -----------------------------------------
        nmsp = \
            {
              "apiVersion": "v1",
              "kind": "Namespace",
              "metadata": {
                "name": batch_namespace,
                "labels": {
                  "name": batch_namespace
                }
              }
            }

        try:
            utils.create_from_dict(k8s_client, nmsp)
        except FailToCreateError:
            print("Namespace already exists. Moving on.")

        #rbac setup -----------------------------------------
        rbac = \
            {'apiVersion': 'rbac.authorization.k8s.io/v1',
             'kind': 'ClusterRole',
             'metadata': {'name': 'aws-batch-cluster-role'},
             'rules': [{'apiGroups': [''], 'resources': ['namespaces'], 'verbs': ['get']},
              {'apiGroups': [''],
               'resources': ['nodes'],
               'verbs': ['get', 'list', 'watch']},
              {'apiGroups': [''],
               'resources': ['pods'],
               'verbs': ['get', 'list', 'watch']},
              {'apiGroups': [''],
               'resources': ['configmaps'],
               'verbs': ['get', 'list', 'watch']},
              {'apiGroups': ['apps'],
               'resources': ['daemonsets', 'deployments', 'statefulsets', 'replicasets'],
               'verbs': ['get', 'list', 'watch']},
              {'apiGroups': ['rbac.authorization.k8s.io'],
               'resources': ['clusterroles', 'clusterrolebindings'],
               'verbs': ['get', 'list']}]}
        try:
            utils.create_from_dict(k8s_client, rbac)
        except FailToCreateError:
            print("Rbac already exists. Moving on.")

        rbac = \
            {'apiVersion': 'rbac.authorization.k8s.io/v1',
             'kind': 'ClusterRoleBinding',
             'metadata': {'name': 'aws-batch-cluster-role-binding'},
             'subjects': [{'kind': 'User',
               'name': 'aws-batch',
               'apiGroup': 'rbac.authorization.k8s.io'}],
             'roleRef': {'kind': 'ClusterRole',
              'name': 'aws-batch-cluster-role',
              'apiGroup': 'rbac.authorization.k8s.io'}}

        try:
            utils.create_from_dict(k8s_client, rbac)
        except FailToCreateError:
            print("Rbac already exists. Moving on.")


        #finalize namespace -----------------------------------------

        fin_nmsp = \
            {'apiVersion': 'rbac.authorization.k8s.io/v1',
             'kind': 'Role',
             'metadata': {'name': 'aws-batch-compute-environment-role',
              'namespace': batch_namespace},
             'rules': [{'apiGroups': [''],
               'resources': ['pods'],
               'verbs': ['create', 'get', 'list', 'watch', 'delete', 'patch']},
              {'apiGroups': [''],
               'resources': ['serviceaccounts'],
               'verbs': ['get', 'list']},
              {'apiGroups': ['rbac.authorization.k8s.io'],
               'resources': ['roles', 'rolebindings'],
               'verbs': ['get', 'list']}]}


        try:
            utils.create_from_dict(k8s_client, fin_nmsp)
        except FailToCreateError:
            print("Final namespace setup already completed. Moving on.")

        fin_nmsp = \
            {'apiVersion': 'rbac.authorization.k8s.io/v1',
             'kind': 'RoleBinding',
             'metadata': {'name': 'aws-batch-compute-environment-role-binding',
              'namespace': batch_namespace},
             'subjects': [{'kind': 'User',
               'name': 'aws-batch',
               'apiGroup': 'rbac.authorization.k8s.io'}],
             'roleRef': {'kind': 'Role',
              'name': 'aws-batch-compute-environment-role',
              'apiGroup': 'rbac.authorization.k8s.io'}}

        try:
            utils.create_from_dict(k8s_client, fin_nmsp)
        except FailToCreateError:
            print("Final namespace setup already completed. Moving on.")


    def _generateQueue(self):

        queue_config = {}
        queue_config["jobQueueName"] = self.queue_name
        queue_config["priority"] = 10
        queue_config["computeEnvironmentOrder"] = \
                [{"order":1,"computeEnvironment":self.computeEnvironmentName}]


        done = False
        for _ in range(3):
            try:
                self.batch_client.create_job_queue(**queue_config)
                done = True
            except Exception as e:
                if "already exists" in str(e):
                    print("Queue already exists. Moving on.")
                    done = True
                    break
                else:
                    print(" Could not create job queue.  Trying again in 30sec.")
                    time.sleep(30)
                pass

        if not done:
            raise ValueError("ERROR: unable to create job queue for the AWS Batch compute environment.")
        else:
            print("AWS Batch created.")

    def terminateBatch( self ) -> None:
        '''
        Deprecated: Use CDK

        When a user is done using an AWS Batch environment,
        this function will terminate both the queue and
        the batch compute environment.

        Returns
        -------
        None

        '''

        #from botocore.exceptions import ClientError

        try:
            #disable queue
            self.batch_client.update_job_queue(jobQueue = self.queue_name,
                                               state='DISABLED')
            time.sleep(15)
        except Exception as e:
            print(e)


        for _ in range(5):
            try:
                #delete queue
                self.batch_client.delete_job_queue(jobQueue = self.queue_name)
                done = True
            except:
                print(" Could not delete job queue.  Trying again in 30sec.")
                time.sleep(30)
                pass


        #disable compute env
        self.batch_client.update_compute_environment(computeEnvironment = self.computeEnvironmentName,
                                                     state='DISABLED')
        #delete compute env
        done = False
        for _ in range(5):
            try:
                self.batch_client.delete_compute_environment(computeEnvironment = self.computeEnvironmentName)
                done = True
            except:
                print(" Could not delete compute environment.  Trying again in 30sec.")
                time.sleep(30)
                pass

        if not done:
            print("ERROR: unable to delete the AWS Batch compute environment.")
        else:
            print("Termination complete.")



    @exponential_backoff()
    def _describe_jobs(self, running_jobs):
        status = self.batch_client.describe_jobs(jobs=running_jobs[:100])['jobs']
        return status

    def wait_for_jobs_finish(self, all_jobs:list[str]) -> None:
        '''
        This is a blocking function that will pause execution
        of python code until all jobs have terminated within
        the specific queue.

        Parameters
        ----------
        all_jobs : list[str]
            Job IDs to monitor for completion. Can be used with
            the 'get_running_jobs' to obtain a list of all currently
            running jobs in the queue.

        Returns
        -------
        None

        '''

        import copy
        if not isinstance(all_jobs,list):
            all_jobs=[all_jobs]
        #remove any duplicates in the list
        all_jobs = list(set(all_jobs))
        running_jobs = copy.deepcopy(all_jobs)
        cnt = 0
        while len(running_jobs) >0:
            cnt+=1

            status = self._describe_jobs(running_jobs)
            # try:
            #     #boto3 only allows an input list of length 100
            #     status = self.batch_client.describe_jobs(jobs=running_jobs[:100])['jobs']
            # except Exception as e:
            #     if "Too Many Requests" in str(e):
            #         time.sleep(1)
            #         continue
            #     else:
            #         raise e
            done_lst = [ x['jobId'] for x in status \
                            if x['status'] == 'FAILED' or x['status'] == 'SUCCEEDED' ]

            for doneid in done_lst:
                #doneid = lst[0]
                if doneid in running_jobs:
                    idx = running_jobs.index(doneid)
                    del running_jobs[idx]

            fraction_done = (1-len(running_jobs)/len(all_jobs)) * 100
            time.sleep(1)
            if cnt % 50==0:
                print("{:.2f}% of jobs have completed.".format(fraction_done))


    @exponential_backoff()
    def kill_jobs(self, jobs:list[str]) -> None:
        '''
        Terminate all jobs provided in this list from a
        specific queue.

        Parameters
        ----------
        jobs : list[str]
            List of job IDs that will be terminated.  Note, this is often
            not instances, i.e. the termination command will be sent
            to Batch, and there may be a delay in seeing termination
            in the AWS Console as Batch graceful to terminates the
            container.

        Returns
        -------
        None

        '''

        for job in jobs:
            self.batch_client.terminate_job(jobId = job,
                                            reason = "No longer needed.")

    def get_running_jobs(self) -> list:
        '''
        Returns a list that containers both the
        job name and the batch defined job ID.  The
        'kill_jobs' and 'wait_for_jobs_finish' only
        require the jobID.

        Returns
        -------
        list
            [job['jobName'] , job['jobId'] ]

        '''

        paginator = self.batch_client.get_paginator('list_jobs')
        jobStatus=['SUBMITTED','PENDING','RUNNABLE','STARTING','RUNNING']
        lst = []
        for status in jobStatus:
            for response in paginator.paginate(jobQueue=self.queue_name, jobStatus=status):
                if 'jobSummaryList' in response.keys():
                    for job in response['jobSummaryList']:
                            lst.append(   [job['jobName'] , job['jobId'] ] )
        return lst



