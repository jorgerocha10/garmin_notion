# Daily Garmin Data Automation Setup Guide

This guide will help you set up automated daily execution of your Garmin data fetching script using GitHub Actions.

## Prerequisites

1. **GitHub Account**: You'll need a GitHub account to use GitHub Actions
2. **API Keys**: Collect all the required API keys and tokens
3. **Initial Setup**: Run the script locally once to ensure everything works

## Step-by-Step Setup

### 1. Push Your Code to GitHub

1. Create a new repository on GitHub
2. Push your code to the repository:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

### 2. Set Up GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

- `EMAIL`: Your Garmin Connect email
- `PASSWORD`: Your Garmin Connect password
- `NOTION_TOKEN`: Your Notion integration token
- `PG_ID`: Your Notion page ID
- `DB_ID`: Your Notion database ID
- `OPENAI_API_KEY`: Your OpenAI API key

### 3. Initial Token Setup (Important!)

Since GitHub Actions runs in a fresh environment each time, you need to extract your Garmin tokens:

**Step 1: Check if you have tokens locally**

1. Run the script locally once: `python garmin/garmin_data.py`
2. If it works (shows "Fetching data for..."), you already have tokens stored locally

**Step 2: Extract tokens for GitHub Actions**

1. Create a temporary script called `get_tokens.py` with this content:

   ```python
   import os
   import base64
   from garth import Client

   token_dir = os.path.expanduser("~/.garminconnect")
   client = Client()
   client.load(token_dir)
   token_data = client.dumps()
   token_base64 = base64.b64encode(token_data.encode()).decode()
   print("GARMINTOKENS_BASE64 =", token_base64)
   ```

2. Run it: `python get_tokens.py`
3. Copy the base64 string from the output
4. Add it to GitHub Secrets as `GARMINTOKENS_BASE64`
5. Delete the temporary script

**Step 3: If you don't have tokens yet**

1. Run `python garmin/garmin_data.py` and complete the login process
2. If MFA is required, enter the code when prompted
3. Once successful, follow Step 2 above to extract the tokens

### 4. Handling MFA (Multi-Factor Authentication)

If your Garmin account has MFA enabled:

- The first run will likely fail
- You might need to temporarily disable MFA for the initial setup
- Once tokens are generated, you can re-enable MFA

### 5. Schedule Configuration

The workflow is set to run daily at 8:00 AM UTC. To change this:

1. Edit `.github/workflows/daily-garmin-fetch.yml`
2. Modify the cron schedule:
   ```yaml
   schedule:
     - cron: "0 8 * * *" # Hour Minute * * *
   ```

Common schedules:

- `0 8 * * *` - 8:00 AM UTC daily
- `0 16 * * *` - 4:00 PM UTC daily
- `0 */6 * * *` - Every 6 hours

### 6. Testing the Setup

1. **Manual trigger**: Go to Actions → Daily Garmin Data Fetch → Run workflow
2. **Check logs**: Monitor the workflow run for any errors
3. **Verify Notion**: Check that data appears in your Notion database

### 7. Troubleshooting

**Common Issues:**

1. **Authentication Errors**:

   - Check that EMAIL and PASSWORD secrets are correct
   - Verify Garmin account credentials
   - Check if MFA is causing issues

2. **Token Issues**:

   - Tokens may expire and need regeneration
   - Run locally to generate fresh tokens
   - Update GARMINTOKENS_BASE64 secret

3. **Notion Errors**:

   - Verify NOTION_TOKEN is correct
   - Check PG_ID and DB_ID are valid
   - Ensure Notion integration has proper permissions

4. **OpenAI Errors**:
   - Verify OPENAI_API_KEY is correct
   - Check API usage limits
   - Ensure you have access to GPT-4 model

**Debugging Steps:**

1. Check the Actions logs for detailed error messages
2. Test individual components locally
3. Verify all secrets are properly set
4. Check Notion database structure matches the code

### 8. Monitoring and Maintenance

- **Check logs regularly**: GitHub Actions provides detailed logs
- **Monitor API usage**: Keep track of OpenAI and Garmin API usage
- **Token refresh**: Garmin tokens may need periodic refresh
- **Notion limits**: Be aware of Notion API rate limits

### 9. Alternative Deployment Options

If GitHub Actions doesn't work for you, consider these alternatives:

1. **Railway**: Easy deployment with cron jobs
2. **Render**: Free tier with cron jobs
3. **Heroku**: Scheduler add-on (paid)
4. **AWS Lambda**: With CloudWatch Events
5. **Google Cloud Functions**: With Cloud Scheduler

### 10. Security Notes

- Never commit API keys or passwords to your repository
- Use GitHub Secrets for all sensitive information
- Consider using environment-specific configurations
- Regularly rotate API keys and tokens

---

## Quick Start Checklist

- [ ] Code pushed to GitHub repository
- [ ] All secrets added to GitHub repository
- [ ] Initial local run completed successfully
- [ ] GARMINTOKENS_BASE64 secret updated
- [ ] Manual workflow run tested
- [ ] Notion data verification completed
- [ ] Schedule configured for your timezone

## Support

If you encounter issues:

1. Check the GitHub Actions logs
2. Test the script locally first
3. Verify all API keys and secrets
4. Check for any API service outages
