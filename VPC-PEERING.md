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

## Before the Call — Information Required from You

Please share the following details with us **before the scheduled call**. This is all we need from you upfront — no AWS configuration changes required beforehand.

| Field              | Description                                          | Example             |
| ------------------ | ---------------------------------------------------- | ------------------- |
| **AWS Account ID** | Your 12-digit AWS Account ID                         | `123456789012`      |
| **AWS Region**     | Region where your VPC resides                        | `eu-west-1`         |
| **VPC ID**         | Your VPC ID                                          | `vpc-0abc123def456` |
| **VPC CIDR Block** | Your VPC CIDR — must not overlap with `10.42.0.0/24` | `10.100.0.0/16`     |

> Once we have these details, we will prepare and send the VPC Peering request during our Thursday call.

---

## Thursday Call — Step by Step

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

## Pre-Call Checklist

**Customer — share before the call:**

- [ ] AWS Account ID
- [ ] AWS Region
- [ ] VPC ID
- [ ] VPC CIDR Block (confirmed no overlap with `10.42.0.0/24`)
- [ ] AWS Console access available during the call

**Us — ready before the call:**

- [ ] All Customer details received and validated
- [ ] Stack deployment prepared with Customer's configuration

---

## Success Criteria

- VPC Peering status is **Active**
- Routes configured on both sides
- DNS resolution enabled
- Connectivity between VPCs verified
