"""
INTERNATIONAL STANDARDS REFERENCE
Implements ISO 8000, ECLASS, UNSPSC, IEC 61360 naming conventions
"""
import yaml
import re
from pathlib import Path

class InternationalStandards:
    """Enforces international naming standards"""
    
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.abbreviations = self.config['standards']['abbreviations']
        self.uom_map = self.config['uom_standardization']
        self.hsn_ref = self.config['hsn_reference']
    
    def apply_abbreviations(self, text):
        """Apply standard abbreviations"""
        text = text.upper()
        for full, abbr in self.abbreviations.items():
            text = text.replace(full.upper(), abbr)
        return text
    
    def standardize_measurement(self, text):
        """Standardize measurement formats per ISO 8000"""
        # Normalize "mm" references
        text = re.sub(r'(\d+)\s*MM', r'\1MM', text)
        text = re.sub(r'(\d+)\s*SQ\s*MM', r'\1SQMM', text)
        text = re.sub(r'(\d+)\s*SQM', r'\1SQMM', text)
        
        # Normalize inches
        text = re.sub(r'(\d+(?:\.\d+)?)\s*"|\'\'|INCH|INCHES', r'\1INCH', text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*'", r'\1INCH', text)
        
        # Normalize cores x section
        text = re.sub(r'(\d+)\s*C\s*[Xx]\s*(\d+(?:\.\d+)?)', r'\1C-\2', text)
        
        return text
    
    def standardize_uom(self, uom):
        """Standardize Unit of Measure"""
        if not uom:
            return "UNIT"
        return self.uom_map.get(uom.upper().strip(), uom.upper().strip())
    
    def get_hsn_code(self, material_type, description=""):
        """Get HSN code based on material type and description"""
        combined = f"{material_type} {description}".upper()
        
        # Priority-based matching
        hsn_rules = [
            (["CABLE", "WIRE", "CONDUCTOR"], "8544"),
            (["MCB", "MCCB", "BREAKER", "SWITCHGEAR", "CHANGE OVER", "CONTACTOR", "SWITCH"], "8536"),
            (["LED", "LIGHT", "BULB", "LAMP", "FLOOD LIGHT"], "9405"),
            (["CHOKE", "TRANSFORMER"], "8504"),
            (["BEARING"], "8482"),
            (["FILTER"], "8421"),
            (["BELT"], "4010"),
            (["PUMP"], "8413"),
            (["COMPRESSOR"], "8414"),
            (["VALVE", "NRV"], "8481"),
            (["PIPE", "TUBE"], "7306"),
            (["PVC PIPE", "CPVC PIPE", "UPVC"], "3917"),
            (["FITTING", "TEE", "ELBOW", "SOCKET", "FLANGE", "UNION", "COUPLING"], "7307"),
            (["COPPER FITTING", "BRASS FITTING"], "7412"),
            (["CEMENT", "CONCRETE"], "2523"),
            (["PAINT", "VARNISH", "ENAMEL"], "3209"),
            (["TILE", "MARBLE", "GRANITE", "VITRIFIED"], "6907"),
            (["VEHICLE", "CAR", "SUV", "BUS", "TRUCK"], "8703"),
            (["GENERATOR", "GENSET", "DG"], "8502"),
            (["COMPUTER", "LAPTOP", "DESKTOP", "SERVER"], "8471"),
            (["AC", "AIR CONDITIONING", "CHILLER", "AHU"], "8415"),
            (["LIFT", "ELEVATOR"], "8428"),
            (["DRUG", "MEDICINE", "TABLET", "CAPSULE", "SYRUP", "INJECTION"], "3004"),
            (["EXTINGUISHER", "SPRINKLER", "FIRE"], "8424"),
            (["MOTOR"], "8501"),
            (["PANEL", "DISTRIBUTION BOARD"], "8537"),
            (["LUG", "GLAND", "CABLE TIE"], "8536"),
            (["CONNECTOR", "PLUG", "SOCKET OUTLET"], "8536"),
            (["DIFFUSER", "GRILL"], "7616"),
        ]
        
        for keywords, hsn in hsn_rules:
            if any(kw in combined for kw in keywords):
                return hsn
        
        return self.hsn_ref.get('default', '8479')
    
    def validate_standardized_name(self, name, category):
        """Validate name follows international standards"""
        issues = []
        
        # Check uppercase
        if name != name.upper():
            issues.append("Name must be ALL CAPS per ISO 8000")
        
        # Check no special characters except hyphen
        if re.search(r'[^A-Z0-9\-]', name):
            issues.append("Name contains invalid characters (only A-Z, 0-9, - allowed)")
        
        # Check doesn't start/end with hyphen
        if name.startswith('-') or name.endswith('-'):
            issues.append("Name cannot start or end with hyphen")
        
        # Check no double hyphens
        if '--' in name:
            issues.append("Name contains double hyphens")
        
        # Check minimum components
        parts = name.split('-')
        if len(parts) < 2:
            issues.append("Name must have at least CATEGORY-SPECIFICATION")
        
        return issues
    
    def generate_audit_trail(self, original, standardized, confidence, reasoning):
        """Generate audit trail entry"""
        return {
            "original_name": original,
            "standardized_name": standardized,
            "confidence_score": confidence,
            "reasoning": reasoning,
            "timestamp": None  # Will be filled by engine
        }