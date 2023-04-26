# SSM Tool
--------
A set of tools to interact with SSM Utilities

###
Accounts Lists
-------------
The accounts lists for the tools in this repo should be formatted as a dict with the region as a top level key and every account enabled for that region in a list as the value. You can get a properly formated list of all PCM managed accounts from the most recent run of the AMI Bakery pipeline here s3://ami-bakery-data-056952386373-us-east-1/account_list
```
{
  "af-south-1": [
    "530786275774",
    "584643220196"
  ],
  "ap-east-1": [
    "530786275774",
    "584643220196"
  ],
  ...
}
```

## SSM Parameter Tool
---------
Add, Update or Delete Parameters to the Parameter stores across multiple regions and accounts

dev-arn: arn:aws:states:us-east-1:530786275774:stateMachine:pcm_ssm_parameter_tool_SM

prod-arn: arn:aws:states:us-east-1:747207162522:stateMachine:pcm_ssm_parameter_tool_SM

### Basic functionality
---------
The SSM Parameter tool is a State Machine on AWS which accepts an event as JSON with a job to execute.
 - When a job is begun, the account_list is fetched from s3://pcm-shared-code-530786275774/ssm_tool/accounts_list
 - The accounts are then divided by region and into batches of jobs then uploaded to s3//pcm-shared-code-530786275774/ssm_tool/jobs/{region}
 - Then the State Machine will concurrently fetch batches of jobs from s3 and execute the jobs
 - The execution ends with a final error check to determine if there were any failures across any account/region

### How To
To run a jobs via gitlab pipeline:
 - Checkout a new branch.
 - Set the ENVIRONMENT variable in .gitlab-ci.yml to "prod".
 - Copy one of the sample event JSON files from 'ci/test/events' to 'jobs/parameter_tool/' and edit to suit your needs.
 - Then git add/commit and push. The 'run-parameter-job.sh' script will automatically execute any .json files in the 'jobs/parameter_tool/' folder and display the results in gitlab.
To run jobs locally (Mac and Ubuntu):
 - Copy one of the sample event JSON files from 'ci/test/events' to 'jobs/parameter_tool/' and edit to suit your needs.
 - Run 'scripts/run-parameter-job.sh' script with 'govinator' role.

#### Current options
Currently there are jobs defined for "create", "update", "delete", "rename" or "fix_tags".


Update event:
```
{
    "action": "init",
    "job_action": "update",
    "args": {
        "names_values": {
            "name_of_parameter": "new value"
        },
        "tags": [
            {"Key": "t_environment", "Value": "DEV"},
            {"Key": "t_AppID", "Value": "SVC02522"},
            {"Key": "t_dcl", "Value": "1"},
            {"Key": "test_tag", "Value": "test"}
        ]
    }
}
```

Optionally, a different account list may be provided by uploading to the pcm-shared-code-747207162522 (or 530786275774 for dev) s3 bucket and then passing the s3 key to the event as "accounts_key".

## SSM Deploy Document Tool
A tool to create or update SSM Documents across all regions and optionally share to a list of accounts.

### Basic functionality
---------
The SSM Deploy Document tool is a tool for deploying SSM documents across PCM Managed accounts and regions.
 - When a job is begun the contents of ./documents are uploaded to s3://pcm-shared-code-530786275774/ssm_tool/ssm_documents/
 - If an accounts_key is provided, the account_list is fetched from s3://pcm-shared-code-530786275774/{accounts_key}
 - A job is created for each region with accounts to share for that region if provided. Then the job is uploaded to s3//pcm-shared-code-530786275774/ssm_tool/deploy_document/jobs/{region}
 - Then the State Machine will concurrently run for each region, fetching the SSM Documents from s3 and deploying to the region and sharing to accounts if they were provided.
 - The execution ends with a final error check to determine if there were any failures across any account/region

 ### How To
To run a jobs via gitlab pipeline:
 - Checkout the main branch.
 - Update existing or put new SSM Documents in the ./documents folder. Name the documents the same as you want it to appear in Systems Manager, must be unique and file format must be either JSON or YAML.
 - Then git add/commit and push. The deploy documents pipeline will start and upload the documents then trigger the state_machine and display results on gitlab