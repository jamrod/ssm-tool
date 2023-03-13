# SSM Tool
--------
A tool to interact with SSM Utilities

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
To run a job, copy one of the sample event JSON files from 'ci/test/events' to 'jobs/' and edit to suit your needs. Then git add/commit and push. The 'run-job' script will automatically execute any .json files in the 'jobs/' folder and display the results in gitlab.
Alternately, you can trigger the execution locally in a Linux or Mac environment by running the 'scripts/run-job.sh' script with 'govinator' role.

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