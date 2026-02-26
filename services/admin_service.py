import json
from pathlib import Path

class AdminService:
    @staticmethod
    def get_pricing_config_path() -> Path:
        return Path(__file__).parent.parent / "pricing_config.json"

    @classmethod
    def update_pricing(cls, pricing_data: dict) -> dict:
        config_path = cls.get_pricing_config_path()
        with open(config_path, "w") as f:
            json.dump(pricing_data, f, indent=2)
        return {"message": "Pricing updated successfully", "pricing": pricing_data}

    @classmethod
    def get_pricing(cls) -> dict:
        config_path = cls.get_pricing_config_path()
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "plans": [
                    {
                        "name": "Starter",
                        "price": "1",
                        "period": "month",
                        "description": "Perfect for small clinics",
                        "features": ["Up to 5 doctors", "Unlimited appointments", "Basic scheduling", "Email support"],
                        "popular": False
                    }
                ],
                "annual_discount": 20,
                "currency": "INR",
                "currency_symbol": "₹"
            }
            
    @classmethod
    def get_public_pricing(cls) -> dict:
        config_path = cls.get_pricing_config_path()
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "plans": [
                    {
                        "name": "Small Clinic",
                        "description": "For 1 Doctor / 1 Hospital",
                        "installationPrice": 5001,
                        "monthlyPrice": 1111,
                        "features": [
                            "1 Doctor profile",
                            "1 Hospital",
                            "Appointment management",
                            "Email reminders",
                            "Basic analytics",
                            "Email support",
                        ],
                        "popular": False,
                    },
                    {
                        "name": "Medium (≤5 Drs)",
                        "description": "For up to 5 Doctors in 1 Hospital",
                        "installationPrice": 11000,
                        "monthlyPrice": 2111,
                        "features": [
                            "Up to 5 Doctor profiles",
                            "1 Hospital",
                            "SMS & Email reminders",
                            "Advanced analytics",
                            "Custom booking page",
                            "Payment integration",
                            "Priority support",
                        ],
                        "popular": True,
                    },
                    {
                        "name": "Corporate",
                        "description": "For 10 Doctors & 5 Hospitals",
                        "installationPrice": 21000,
                        "monthlyPrice": 5111,
                        "features": [
                            "Up to 10 Doctor profiles",
                            "Up to 5 Hospitals (same ownership)",
                            "Multi-location support",
                            "Custom integrations",
                            "Dedicated account manager",
                            "24/7 phone support",
                            "White-label option",
                        ],
                        "popular": False,
                    },
                ],
                "currency": "INR",
                "currency_symbol": "₹",
                "invoiceLabels": {
                    "installationFee": "One-Time Software Activation & License Fee",
                    "monthlyFee": "Monthly Technical Support & Maintenance Charges"
                }
            }
