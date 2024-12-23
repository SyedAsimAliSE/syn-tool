# SAP-Shopify Sync Tool

## Requirements
items sap to shopify.
orders shopify to sap.
payment shopify to sap.
credits shopify to sap.

## Prerequisites

1. **Python Installation**
   ```powershell
   # Download Python 3.8 or later from https://www.python.org/downloads/
   # During installation:
   # ✓ Add Python to PATH
   # ✓ Install pip
   ```

2. **Git Installation**
   ```powershell
   # Download Git from https://git-scm.com/download/windows
   # Use default installation options
   ```

## Project Setup

1. **Clone the Repository**
   ```powershell
   # Open PowerShell and navigate to desired directory
   cd C:\Projects
   git clone <repository-url>
   cd syn-tool
   ```

2. **Create Virtual Environment**
   ```powershell
   # Create a new virtual environment
   python -m venv venv

   # Activate the virtual environment
   .\venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```powershell
   # Upgrade pip
   python -m pip install --upgrade pip

   # Install requirements
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```powershell
   # Copy example environment file
   copy .env.example .env

   # Open .env in notepad to edit
   notepad .env

   ```

## Verify Installation

1. **Test Connections**
   ```powershell
   # Test SAP connection
   python -m syn_tool test connection sap

   # Test Shopify connection
   python -m syn_tool test connection shopify
   ```

2. **List Available Commands**
   ```powershell
   python -m syn_tool --help
   ```

## Common Issues and Solutions

1. **Python Command Not Found**
    - Ensure Python is added to PATH during installation
    - Restart PowerShell after installation

2. **Permission Issues**
    - Run PowerShell as Administrator
    - Check Windows Defender settings

3. **SSL Certificate Errors**
    - Update certificates:
   ```powershell
   pip install --upgrade certifi
   ```

4. **Virtual Environment Activation Error**
    - If you get execution policy error:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

## Development Tools

1. **Install Visual Studio Code**
    - Download from https://code.visualstudio.com/
    - Install Python extension

2. **Configure VS Code**
   ```json
   {
       "python.defaultInterpreterPath": "${workspaceFolder}\\venv\\Scripts\\python.exe",
       "python.linting.enabled": true,
       "python.formatting.provider": "black"
   }
   ```

3. **Install Additional Tools**
   ```powershell
   pip install black pylint pytest
   pip install pdoc
   ```

## Usage

SyncManager: Coordinates all operations
ProductService: Handles product synchronization
OrderService: Handles order synchronization
PaymentService: Handles payment synchronization
CreditService: Handles credit and refund synchronization
TestService: Handles all testing operations

# Commands for debugging
Note that these are just used for the development purposes.
and are not supposed to be used in production.

```bash
python -m syn_tool describe entity group sap
python -m syn_tool describe entity group shopify
python -m syn_tool describe list group sap
python -m syn_tool describe list group sap --id 117
python -m syn_tool describe list group shopify --id 1032025
python -m syn_tool describe mapping group
python -m syn_tool sync group --direction sap-to-shopify --mode full
```

# List items in a group

```bash
python -m syn_tool group list-items sap --group-id 100 # there is only one group with items in it.
python -m syn_tool group list-items shopify --name "Items"
python -m syn_tool group list-items shopify --name "Adaptor for carbide planer blades"
```

# Sync specific groups

```bash
python -m syn_tool group sync sap-to-shopify --group-id 100
```

# Sync all groups with their items
```bash
python -m syn_tool group sync both --with-items  
```

# View group details

```bash
python -m syn_tool describe group sap --id "G001"
python -m syn_tool describe group shopify --name "Summer Collection"

```

# will tell us about the items

```bash
python -m syn_tool group debug-items --source sap --verbose

#20 items total, all in group 100 (Items)
#All other groups (101-117) are currently empty
#Items have detailed information including ItemCode, ItemName, ItemsGroupCode, etc.
```

```bash
python -m syn_tool group debug-items --source shopify --verbose

#250 products total
#50 collections (equivalent to SAP groups)
#Most collections have products, but some like "Building Tools" and "Clamping & Mounting" are empty
#Products have basic information like title, vendor, product_type, images, etc.
```

```bash
python -m syn_tool group check-items --source sap --show-incomplete

#All 20 items are missing prices
#They all have SKUs (item codes), names, and stock information
```

```bash
python -m syn_tool group check-items --source shopify --show-incomplete

#229 products have complete information (SKU, title, price, inventory)
#21 products are missing some information

```

### SYNC > SAP > SHOPIFY
```bash
#SYNC GROUP SAP TO SHOPIFY by group id
python -m syn_tool group list --source sap
python -m syn_tool group sync sap-to-shopify --group-id 100  ##<< you need to get the id from the list command
python -m syn_tool group sync sap-to-shopify --group-id 100 --with-items ##<< will sync products along with the group
python -m syn_tool describe list group shopify ##<< to verify that the sync was successful
python -m syn_tool group list --source shopify ##<< to verify that the sync was successful

## Partially implemented for testing purposes not required.
python -m syn_tool group list --source shopify
python -m syn_tool group sync shopify-to-sap --group-id 469889417533
python -m syn_tool group list --source sap

#SYNC ORDERS FROM SHOPIFY TO SAP
python -m syn_tool order describe #<< for development
python -m syn_tool order list --limit 5 #<< to get the order id
python -m syn_tool order status 6239897223485 #<< to get the order status
python3 -m syn_tool sync orders --mode incremental --batch-size 5 # << to sync the orders
python3 -m syn_tool order sync --order-id 6239897223485 # << to sync a single order

```

```bash
#FOR DEBUGGING PURPOSES
python -m syn_tool group list-items shopify --group-id "6239897223485"
python -m syn_tool group list-items shopify --group-id "6239897223485" --status active
python -m syn_tool group list-items shopify --group-id "6239897223485" --search "10mm"
python -m syn_tool group list-items shopify --group-id "6239897223485" --format json
python -m syn_tool group list-items shopify --group-id "6239897223485" --status active --search "10mm" --format json


python3 -c from syn_tool.clients.sap_client import SAPClient; from syn_tool.core.config import SAPConfig; config =
SAPConfig.from_env(); client = SAPClient(config); client.patch('BusinessPartners(\'C1444\')', {'Valid': 'tYES', '
ValidFrom': '2024-12-19', 'ValidTo': '2099-12-31', 'Frozen': 'tNO', 'Block': 'tNO', 'PaymentBlock': 'tNO', 'CardType': '
cCustomer', 'FatherType': 'cPayments_sum', 'Currency': 'AUD', 'GroupCode': 100})

env PYTHONPATH=/home/sim/Desktop/shell/syn-tool python3 -c from syn_tool.clients.sap_client import SAPClient; from
syn_tool.core.config import SAPConfig; config = SAPConfig.from_env(); client = SAPClient(config); client.patch('
BusinessPartners(\'C1444\')', {'Valid': 'tYES', 'ValidFrom': '2024-12-19', 'ValidTo': '2099-12-31', 'Frozen': 'tNO', '
Block': 'tNO', 'PaymentBlock': 'tNO', 'CardType': 'cCustomer', 'FatherType': 'cPayments_sum', 'Currency': 'AUD', '
GroupCode': 100, 'VatLiable': 'vLiable', 'PriceListNum': 1, 'SalesPersonCode': 1, 'DebitorAccount': '140000', '
BackOrder': 'tYES', 'PartialDelivery': 'tYES'})

env PYTHONPATH=/home/sim/Desktop/shell/syn-tool python3 -c from syn_tool.clients.sap_client import SAPClient; from
syn_tool.core.config import SAPConfig; config = SAPConfig.from_env(); client = SAPClient(config); print(client.get('
BusinessPartners(\'C1444\')'))

env PYTHONPATH=/home/sim/Desktop/shell/syn-tool python3 -c from syn_tool.clients.sap_client import SAPClient; from
syn_tool.core.config import SAPConfig; config = SAPConfig.from_env(); client = SAPClient(config); client.patch('
BusinessPartners(\'C1444\')', {'Properties1': 'tYES', 'Properties2': 'tYES', 'Properties3': 'tYES', 'Properties4': '
tYES', 'Properties5': 'tYES', 'Properties6': 'tYES', 'Properties7': 'tYES', 'Properties8': 'tYES', 'Properties9': '
tYES', 'Properties10': 'tYES'})

env PYTHONPATH=/home/sim/Desktop/shell/syn-tool python3 -c from syn_tool.clients.sap_client import SAPClient; from
syn_tool.core.config import SAPConfig; config = SAPConfig.from_env(); client = SAPClient(config); print(
client.session.get('https://203.143.87.235:50000/b1s/v1/$metadata').text)

```






