# SSM Tool
--------
A set of tools to interact with SSM Utilities

 - Parameter tool : Create, Update or Delete parameters accross a list of accounts
 - Deploy Document tool : Create or Update SSM Documents and optionally share to a list of accounts
 - Run Document tool : Run SSM Document in accounts

###
Accounts Lists
-------------
The accounts lists for the tools in this repo should be formatted as a dict with the region as a top level key and every account enabled for that region in a list as the value. You can get a properly formated list of all PCM managed accounts from the most recent run of the AMI Bakery pipeline here s3://ami-bakery-data-056952386373-us-east-1/account_list
```
{
  "af-south-1": [
    "acct1",
    "acct2"
  ],
  "ap-east-1": [
    "acct1",
    "acct2"
  ],
  ...
}
```

## SSM Parameter Tool
---------
Add, Update or Delete Parameters to the Parameter stores across multiple regions and accounts

dev-arn: arn:aws:states:us-east-1:acct1:stateMachine:pcm_ssm_parameter_tool_SM

prod-arn: arn:aws:states:us-east-1:acct3:stateMachine:pcm_ssm_parameter_tool_SM

### Basic functionality
---------
The SSM Parameter tool is a State Machine on AWS which accepts an event as JSON with a job to execute.
 - When a job is begun, the account_list is fetched from s3://my-bucket-acct1/ssm_tool/accounts_list
 - The accounts are then divided by region and into batches of jobs then uploaded to s3//my-bucket-acct1/ssm_tool/jobs/{region}
 - Then the State Machine will concurrently fetch batches of jobs from s3 and execute the jobs
 - The execution ends with a final error check to determine if there were any failures across any account/region

### How To
-----
To run a jobs via gitlab pipeline:
 - Checkout a new branch.
 - Set the ENVIRONMENT variable in .gitlab-ci.yml to PRD.
 - Set the RUN_PARAMETER_JOBS variable in the .gitlab-ci.yaml to 'true'
 - Copy one of the sample event JSON files from 'ci/test/events' to 'jobs/parameter_tool/' and edit to suit your needs.
 - Then git add/commit and push. The 'run-parameter-job.sh' script will automatically execute any .json files in the 'jobs/parameter_tool/' folder and display the results in gitlab.
To run jobs locally (Mac and Ubuntu):
 - Copy one of the sample event JSON files from 'ci/test/events' to 'jobs/parameter_tool/' and edit to suit your needs.
 - Run 'scripts/run-parameter-job.sh' script with 'govinator' role.

#### Current options
Currently there are jobs defined for "create", "update", "delete", "rename" or "fix_tags".

#### Anatomy of a job.json
JSON for all jobs have three keys,
 - "*action*": Always "init" for all jobs
 - "*job_action*": Set to one of "create", "update", "delete", "rename" or "fix_tags"
 - "*args*": A dictionary which defines the information specific to the job

##### Create
There is a "names_values" dictionary in "args" which contains key value pairs representing the parameters you would like to add.
There is a "tags" list which has tags to be applied to the new parameter as dictionaries containing "Key": "key_name", "Value: "value" pairs

Create Example
```
{
    "action": "init",
    "job_action": "create",
    "args": {
        "names_values": {
            "new_parameter_name": "new parameter value"
        },
        "tags": [
            {"Key": "t_environment", "Value": "DEV"},
            {"Key": "t_AppID", "Value": ""},
            {"Key": "t_dcl", "Value": "1"}
        ]
    }
}
```

##### Update
There is a "names_values" dictionary in "args" which contains key value pairs representing the parameters you would like to update and the new value for those parameters.
There is a "tags" list which has tags to be applied to the updated parameter as dictionaries containing "Key": "key_name", "Value: "value" pairs

Update:
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
            {"Key": "t_AppID", "Value": ""},
            {"Key": "t_dcl", "Value": "1"},
            {"Key": "test_tag", "Value": "test"}
        ]
    }
}
```

#### Delete
In the case of "delete" the "args" contains a "names" list which has the name of any parameter you would like to remove from the parameter store.

Delete example:
```
{
    "action": "init",
    "job_action": "remove",
    "args": {
        "names": [
            "name_of_parameter_to_delete"
        ]
    }
}
```



Optionally, a different account list may be provided by uploading to the my-bucket-acct3 (or acct1 for dev) s3 bucket and then passing the s3 key to the event as "accounts_key".

## SSM Deploy Document Tool
A tool to create or update SSM Documents across all regions and optionally share to a list of accounts.

### Basic functionality
---------
The SSM Deploy Document tool is a tool for deploying SSM documents across PCM Managed accounts and regions.
 - When a job is begun the contents of ./documents are uploaded to s3
    - DEV bucket : s3://my-bucket-acct1/ssm_tool/ssm_documents/
    - PRD bucket : s3://my-bucket-acct3/ssm_tool/ssm_documents/
 - If an accounts_key is provided, the account_list is fetched from {S3BUCKET}/{accounts_key}
 - A job is created for each region with accounts to share for that region if provided. Then the job is uploaded to {S3BUCKET}/ssm_tool/deploy_document/jobs/{region}
 - Then the State Machine will concurrently run for each region, fetching the SSM Documents from s3 and deploying to the region and sharing to accounts if they were provided.
 - The execution ends with a final error check to determine if there were any failures across any account/region

 ### How To
To run a jobs via gitlab pipeline:
 - Checkout the main branch.
 - Update existing or put new SSM Documents in the ./documents folder. Name the documents the same as you want it to appear in Systems Manager, must be unique and file format must be either JSON or YAML.\
 - Set variables at the top of .gitlab-ci.yml
    - ENVIRONMENT : DEV to test, PRD to deploy
    - SHARE_ACCOUNTS_KEY : Leave as ssm_tool/accounts_list unless you want to specify a list of accounts
    - GET_PCM_ACCOUNTS: Set to 'true' to run state machine which collects a list of all PCM managed accounts which will then have the document shared to, SHARE_ACCOUNTS_KEY is the output key
    - DEPLOY_DOCUMENTS: Set to 'true' to deploy documents to all accounts
 - Then git add/commit and push. The deploy documents pipeline will start and upload the documents then trigger the state_machine and display results on gitlab

## SSM Run Document Tool
A tool to run documents on instances

### Basic functionality
---------
The SSM Run Document tool is designed to concurrently run documents on AWS EC2 instances across multiple accounts and regions. The run document tool is a State Machine on AWS which accepts an event as JSON with a job to execute. The JSON event has two top level parameters "action" which should always be "init" and "arguments". The "arguments" parameter has two parameters: "document" which is the name of the document to run and "parameters" which contains a JSON string with any parameters which need to be passed to the document. The document must exist in the account and region in which it is to be run, use the SSM Deploy Document tool to achieve this. The instance list must exist on S3 in my-bucket-acct1/ssm_tool/run_document/instance_list for dev or my-bucket-acct3/ssm_tool/run_document/instance_list for prod and should be formatted as
```
{
  "region-name": {
      "account-number": ["instance-id", "instance-id"]
}
```
There is no pipeline established for running the Run Document tool


## Tests
-----

The repository includes a comprehensive local testing framework using AWS SAM Local to test Lambda functions without deploying to AWS.

### Prerequisites
- **AWS SAM CLI** installed (`brew install aws-sam-cli` or [AWS documentation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- **Docker** running (required for SAM Local)
- **aws-runas** tool for credential management
- **CDK deployment** completed (templates must exist in `cdk.out/` directory)

### Test Structure

#### Test Components
- **`ci/test/test-stack.sh`** - Main test execution script
- **`ci/test/make_env.py`** - Generates environment variables from `stage_parameters.json`
- **`ci/test/events/`** - Sample event payloads for each lambda function
- **`ci/test/envs/`** - Generated environment variable files (auto-created)
- **`stage_parameters.json`** - Central configuration for all environments and lambdas

#### Available Test Events
- `ssm_parameter_tool.json` - Test parameter tool with create action
- `create.json`, `update.json`, `delete.json` - Various parameter actions
- `fix_tags.json` - Tag fixing operations
- `document/` - Document-related test events

### How to Run Tests

#### Test SSM Parameter Tool
```bash
# Test parameter tool in dev environment
bash ci/test/test-stack.sh ssm_parameter_tool dev

# Test parameter tool in prod environment
bash ci/test/test-stack.sh ssm_parameter_tool prod
```

#### Test Other Lambdas
```bash
# Test document deployment tool
bash ci/test/test-stack.sh ssm_deploy_document_tool dev

# Test document run tool
bash ci/test/test-stack.sh ssm_run_document_tool dev
```

### What the Tests Do

1. **Environment Setup**: Automatically generates environment variables from `stage_parameters.json` for the specified stage
2. **Local Invocation**: Uses SAM Local to invoke the Lambda function with proper CloudFormation templates
3. **Real AWS Resources**: Tests interact with actual AWS resources (S3, SSM, etc.) in the specified environment
4. **Event Simulation**: Uses realistic event payloads that match what the State Machine would send

### Creating Custom Test Events

To test with custom scenarios:

1. **Copy an existing event**:
   ```bash
   cp ci/test/events/ssm_parameter_tool.json ci/test/events/my_test.json
   ```

2. **Edit the event** to match your test case:
   ```json
   {
       "action": "init",
       "job_action": "create",
       "args": {
           "names_values": {
               "my_test_param": "test-value"
           }
       }
   }
   ```

3. **Run with custom event**:
   ```bash
   # Modify test-stack.sh to use your custom event file
   ```

### Test Configuration

The `stage_parameters.json` file contains all environment-specific configuration:
- **DEV**: Uses account `acct1`
- **PRD**: Uses account `acct3`
- **S3 Buckets**: Stage-specific bucket names
- **IAM Roles**: Cross-account role names
- **Environment Tags**: Environment-specific tagging

### Debugging Tests

#### View Lambda Logs
SAM Local outputs logs directly to the terminal, including:
- Lambda function output
- Error messages and stack traces
- AWS SDK calls and responses

#### Test Individual Components
Each Lambda also includes inline testing code for quick local debugging:
```python
# For direct Python testing (at bottom of lambda files)
test_event = {"action": "run_job", "job_key": "ssm_tool/jobs/us-west-2/batch-2"}
print(main(app=app_instance_, event=test_event))
```

### Best Practices

1. **Test Before Deployment**: Always run tests locally before deploying changes
2. **Use DEV Environment**: Test against DEV environment first to avoid production impact
3. **Clean Up**: Be aware that tests interact with real AWS resources - clean up test data as needed
4. **Validate Permissions**: Ensure your AWS credentials have appropriate permissions for the test environment
