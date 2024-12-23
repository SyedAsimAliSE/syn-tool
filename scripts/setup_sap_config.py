#!/usr/bin/env python3

import os
import sys
import json
import requests
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class SAPSetup:
    def __init__(self):
        """Initialize SAP setup using environment variables."""
        self.service_url = os.getenv('SAP_API_URL', '').rstrip('/')
        self.company_db = os.getenv('SAP_COMPANY_DB')
        self.username = os.getenv('SAP_USERNAME')
        self.password = os.getenv('SAP_PASSWORD')
        
        if not all([self.service_url, self.company_db, self.username, self.password]):
            print("Error: Missing SAP credentials in .env file")
            print("Required: SAP_API_URL, SAP_COMPANY_DB, SAP_USERNAME, SAP_PASSWORD")
            sys.exit(1)
            
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({'Content-Type': 'application/json'})
        self._login()

    def _login(self):
        """Login to SAP B1 Service Layer."""
        login_data = {
            'CompanyDB': self.company_db,
            'UserName': self.username,
            'Password': self.password
        }
        response = self.session.post(
            f'{self.service_url}/Login',
            data=json.dumps(login_data)
        )
        response.raise_for_status()
        print("Successfully logged into SAP B1")

    def get_branches(self) -> Dict:
        """Get list of branches/business places."""
        response = self.session.get(f'{self.service_url}/BusinessPlaces')
        response.raise_for_status()
        return response.json()

    def get_tax_codes(self) -> Dict:
        """Get list of tax codes."""
        response = self.session.get(f'{self.service_url}/VatGroups')
        response.raise_for_status()
        return response.json()

    def get_accounts(self) -> Dict:
        """Get list of G/L accounts."""
        response = self.session.get(
            f'{self.service_url}/ChartOfAccounts',
            params={'$filter': 'AccountType eq \'at_Revenue\''}
        )
        response.raise_for_status()
        return response.json()

    def get_customer_groups(self) -> Dict:
        """Get list of business partner groups."""
        response = self.session.get(f'{self.service_url}/BusinessPartnerGroups')
        response.raise_for_status()
        return response.json()

    def create_customer_group(self, name: str) -> Dict:
        """Create a new customer group."""
        data = {
            'Name': name,
            'Type': 'cCustomer'
        }
        response = self.session.post(
            f'{self.service_url}/BusinessPartnerGroups',
            data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    def create_tax_code(self, code: str = "X0", name: str = "No Tax", rate: float = 0.0) -> Dict:
        """Create a new tax code."""
        data = {
            "Code": code,
            "Name": name,
            "Rate": rate,
            "Category": "bovcOutputTax",  # Output VAT
            "IsSystem": "tNO"
        }
        response = self.session.post(
            f'{self.service_url}/VatGroups',
            data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

    def create_revenue_account(self, code: str = "410000", name: str = "Sales Revenue") -> Dict:
        """Create a revenue account."""
        data = {
            "Code": code,
            "Name": name,
            "AccountLevel": "3",  # Detail account
            "AccountType": "at_Revenue",
            "IsControlAccount": "tNO"
        }
        response = self.session.post(
            f'{self.service_url}/ChartOfAccounts',
            data=json.dumps(data)
        )
        response.raise_for_status()
        return response.json()

def update_env_file(config: Dict):
    """Update .env file with new configurations."""
    env_path = Path(__file__).parent.parent / '.env'
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    env_dict = {}
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            env_dict[key.strip()] = value.strip()
    
    env_dict.update({
        'SAP_BRANCH_ID': str(config['branch_id']),
        'SAP_TAX_CODE': config['default_tax_code'],
        'SAP_REVENUE_ACCOUNT': config['revenue_account'],
        'SAP_CUSTOMER_GROUP': str(config['default_customer_group'])
    })
    
    with open(env_path, 'w') as f:
        for key, value in sorted(env_dict.items()):
            if ' ' in str(value):
                value = f'"{value}"'
            f.write(f'{key}={value}\n')
    
    print(f"\nUpdated .env file at: {env_path}")

def main():
    setup = SAPSetup()

    print("\nUsing default configuration values...")
    
    branch_id = 1
    tax_code = "X0"
    account_code = "410000"
    group_code = 100

    print(f"Branch ID: {branch_id}")
    print(f"Default Tax Code: {tax_code}")
    print(f"Revenue Account: {account_code}")
    print(f"Customer Group Code: {group_code}")

    config = {
        'branch_id': branch_id,
        'default_tax_code': tax_code,
        'revenue_account': account_code,
        'default_customer_group': group_code
    }

    update_env_file(config)
    
    print("\nConfiguration complete! The following values have been added to your .env file:")
    print(f"SAP_BRANCH_ID={branch_id}")
    print(f"SAP_TAX_CODE={tax_code}")
    print(f"SAP_REVENUE_ACCOUNT={account_code}")
    print(f"SAP_CUSTOMER_GROUP={group_code}")
    print("\nNote: These are default values. Please update them in your .env file if they differ in your SAP system.")

if __name__ == '__main__':
    main()
