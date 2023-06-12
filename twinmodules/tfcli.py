# -*- coding: utf-8 -*-
######################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. #
# SPDX-License-Identifier: MIT-0                                     #
######################################################################

from twinmodules.AWSModules import AWS_ECR
from twinmodules.core.util import get_user_json_config
from twinmodules.AWSModules.AWSBatch import batch


#%% main
if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', dest='inputfile',   type=str, help="json inputs for command line options. " )
    parser.add_argument('-d', dest='dockerfile',  type=str, help="dockerfile (including path) to be built and pushed to ECR. Only used if -i not given. " )
    parser.add_argument('--region', dest='region',type=str, help="AWS region. Only used if -i not given. " )
    parser.add_argument('-t', dest='tag',         type=str, help="ECR repo name to use. Only used if -i not given. " )
    parser.add_argument('-bp', dest='build_and_push',action='store_true', default=False, help="Build a docker image and push to ECR." )
    parser.add_argument('-bs', dest='batch_status', default=False, action='store_true', help="Get running jobs in batch." )
    parser.add_argument('-bq', dest='batch_queue', type=str, help="Batch queue to review." )
    parser.add_argument('-k', dest='batch_kill', action='store_true', default=False, help="Kill batch jobs" )
    args = parser.parse_args()


    if args.build_and_push:
        if args.inputfile is not None:
            config = get_user_json_config(args.inputfile)
            AWS_ECR.containerize( config["region"],
                                  config["ecr_build"])
        elif args.dockerfile is not None \
            and args.region is not None  \
                and args.tag is not None:

            dockerfile = [{args.tag: args.dockerfile}]
            AWS_ECR.containerize( args.region,
                                  dockerfile)
        else:
            raise ValueError("ERROR: Must either provide json input or -d, -t, --region input options. ")

    if args.batch_status:
        #infrasctructure is dummy here since we are only grabbing status
        mybatch = batch(infrastructure_type='eks',
                        queue_name=args.batch_queue
                        )
        print(mybatch.get_running_jobs())

    if args.batch_kill:
        if args.batch_queue is None:
            raise ValueError("ERROR: must provide the queue name.")

        #infrasctructure is dummy here since we are only grabbing status
        mybatch = batch(infrastructure_type='eks',
                        queue_name=args.batch_queue
                        )
        running_jobs = mybatch.get_running_jobs()
        if len(running_jobs) > 0:
            job_id = [x[1] for x in running_jobs]
            mybatch.kill_jobs(job_id)
            print("Killed:", job_id)
        else:
            print("No jobs in queue.")
