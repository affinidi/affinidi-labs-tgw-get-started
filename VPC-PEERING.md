# VPC Peering Setup Guide

## Overview

We will establish a **VPC Peering connection** between your AWS account and our AWS environment to enable private communication.

- Our VPC CIDR: `10.42.0.0/24`
- Your VPC CIDR must **not overlap** with this range

---

## Architecture

```
+------------------------+          +------------------------+
|   Customer AWS Account |          |   Affinidi AWS Account |
|                        |          |                        |
|   VPC (Customer CIDR)  |<-------->|   VPC (10.42.0.0/24)  |
|                        |  Peering |                        |
|   Route Tables         |          |   Route Tables         |
+------------------------+          +------------------------+

Customer adds route   ---> 10.42.0.0/24 via Peering Connection
We add route          ---> Customer CIDR via Peering Connection

DNS Resolution enabled on both sides
```

---

## Before the Setup Session — Actions Required from You

There are two things we need from you before the scheduled call.

---

### Step 1: Create an IAM Role in Your AWS Account

**Why this is needed:** Our deployment stack uses AWS CloudFormation to manage the VPC Peering connection. When peering across accounts, CloudFormation (running in our account) needs to assume a role in your account in order to accept the peering connection. This is a standard AWS requirement for cross-account VPC peering via CloudFormation.

> Reference: [AWS CloudFormation — Peer with a VPC in another account](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/peer-with-vpc-in-another-account.html)

#### Trust Policy

This grants our AWS account permission to assume the role. Use the following:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::AFFINIDI_ACCOUNT_ID:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

> Replace `AFFINIDI_ACCOUNT_ID` with the account ID we will share with you.

#### Permission Policy

The only permission required is to accept the VPC Peering connection on our behalf:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ec2:AcceptVpcPeeringConnection",
      "Resource": "*"
    }
  ]
}
```

You can name the role anything descriptive, e.g. `affinidi-peering-role`.

Once created, please share the **IAM Role ARN** with us (e.g. `arn:aws:iam::123456789012:role/affinidi-peering-role`).

---

### Step 2: Share the Following Details with Us

| Field              | Description                                          | Example                                                |
| ------------------ | ---------------------------------------------------- | ------------------------------------------------------ |
| **IAM Role ARN**   | ARN of the role created above                        | `arn:aws:iam::123456789012:role/affinidi-peering-role` |
| **AWS Account ID** | Your 12-digit AWS Account ID                         | `123456789012`                                         |
| **AWS Region**     | Region where your VPC resides                        | `eu-west-1`                                            |
| **VPC ID**         | Your VPC ID                                          | `vpc-0abc123def456`                                    |
| **VPC CIDR Block** | Your VPC CIDR — must not overlap with `10.42.0.0/24` | `10.100.0.0/16`                                        |

> Once we have these details, we will prepare and send the VPC Peering request during our setup session.

---

## Setup Session — Step by Step

### 1. We Send the VPC Peering Request

Using our deployment stack with the details provided by Customer, we will send the VPC Peering Connection request from our AWS account to Customer's VPC.

---

### 2. Customer: Accept the Peering Connection

1. Go to **VPC → Peering Connections** in the AWS Console
2. Find the pending request (requester will be our AWS account)
3. Select it and click **Actions → Accept Request**

---

### 3. Customer: Add Routes to Our CIDR Block

For each relevant route table (typically private subnets that need to reach our services):

1. Go to **VPC → Route Tables**
2. Select the route table → **Routes → Edit Routes**
3. Add a new route:
   - **Destination:** `10.42.0.0/24`
   - **Target:** The VPC Peering Connection accepted above
4. Save

---

### 4. Customer: Enable DNS Resolution

1. Go to **VPC → Peering Connections**
2. Select the active peering connection
3. Click **Actions → Edit DNS Settings**
4. Enable **DNS resolution from remote VPC**
5. Save

---

### 5. Both: Verify Connectivity

Once all steps above are complete, we will test end-to-end connectivity between both VPCs.

---

## Pre-Session Checklist

**Customer — complete before the session:**

- [ ] IAM Role created with the trust and permission policies above
- [ ] IAM Role ARN shared with us
- [ ] AWS Account ID shared
- [ ] AWS Region shared
- [ ] VPC ID shared
- [ ] VPC CIDR Block shared (confirmed no overlap with `10.42.0.0/24`)
- [ ] AWS Console access available during the call

**Us — ready before the session:**

- [ ] Affinidi AWS Account ID shared with customer (needed for trust policy)
- [ ] All customer details received and validated
- [ ] Stack deployment prepared with customer's configuration

---

## Success Criteria

- VPC Peering status is **Active**
- Routes configured on both sides
- DNS resolution enabled
- Connectivity between VPCs verified
