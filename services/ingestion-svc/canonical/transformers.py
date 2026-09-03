"""Data transformers for converting raw data to canonical format."""

from typing import Dict, Any, Optional, List
from datetime import datetime, date
import re
import logging

logger = logging.getLogger(__name__)

class DataTransformer:
    """Transform raw data to canonical format."""
    
    def __init__(self):
        self.field_mappings = self._initialize_field_mappings()
        self.normalizers = self._initialize_normalizers()
    
    def _initialize_field_mappings(self) -> Dict[str, str]:
        """Initialize field name mappings."""
        return {
            # Document fields
            'invoice_number': 'document_number',
            'invoice #': 'document_number',
            'po_number': 'purchase_order',
            'purchase_order': 'purchase_order',
            'order_number': 'reference_number',
            
            # Date fields
            'invoice_date': 'document_date',
            'date': 'document_date',
            'due_date': 'due_date',
            'delivery_date': 'delivery_date',
            
            # Vendor fields
            'vendor_name': 'vendor.name',
            'vendor': 'vendor.name',
            'supplier': 'vendor.name',
            'vendor_tax_id': 'vendor.tax_id',
            'tax_id': 'vendor.tax_id',
            'vendor_address': 'vendor.address',
            'vendor_address1': 'vendor.address',
            'vendor_city': 'vendor.city',
            'vendor_state': 'vendor.state',
            'vendor_country': 'vendor.country',
            'vendor_zip': 'vendor.postal_code',
            'vendor_postal': 'vendor.postal_code',
            
            # Buyer fields
            'buyer_name': 'buyer.name',
            'customer': 'buyer.name',
            'buyer_department': 'buyer.department',
            'buyer_address': 'buyer.address',
            'buyer_city': 'buyer.city',
            'buyer_state': 'buyer.state',
            
            # Financial fields
            'total': 'total_amount',
            'amount': 'total_amount',
            'grand_total': 'total_amount',
            'subtotal': 'subtotal',
            'tax': 'tax_total',
            'tax_amount': 'tax_total',
            'shipping': 'shipping_total',
            'discount': 'discount_total',
            
            # Payment fields
            'payment_terms': 'payment_terms',
            'terms': 'payment_terms',
            'payment_method': 'payment_method',
            
            # Currency
            'currency': 'currency',
        }
    
    def _initialize_normalizers(self) -> Dict[str, callable]:
        """Initialize value normalizers."""
        return {
            'amount': self._normalize_amount,
            'date': self._normalize_date,
            'vendor_name': self._normalize_vendor_name,
            'tax_id': self._normalize_tax_id,
        }
    
    async def transform(
        self,
        raw_data: Dict[str, Any],
        extraction_result: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Transform raw data to canonical format.
        
        Args:
            raw_data: Raw data from extraction
            extraction_result: Optional extraction result for additional context
            
        Returns:
            Transformed data ready for validation
        """
        canonical_data = {}
        
        # Step 1: Map fields
        canonical_data = self._map_fields(raw_data)
        
        # Step 2: Normalize values
        canonical_data = self._normalize_values(canonical_data)
        
        # Step 3: Extract additional data from extraction result
        if extraction_result:
            canonical_data = self._extract_from_extraction(canonical_data, extraction_result)
        
        # Step 4: Create structured objects
        canonical_data = self._structure_data(canonical_data)
        
        # Step 5: Add metadata
        canonical_data['processed_at'] = datetime.now().isoformat()
        
        logger.debug(f"Transformed data: {canonical_data.keys()}")
        return canonical_data
    
    def _map_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map raw field names to canonical field names."""
        mapped = {}
        
        for key, value in data.items():
            # Check if key is in mappings
            canonical_key = self.field_mappings.get(key.lower())
            
            if canonical_key:
                # Handle nested keys
                if '.' in canonical_key:
                    parts = canonical_key.split('.')
                    current = mapped
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = value
                else:
                    mapped[canonical_key] = value
            else:
                # Keep unknown fields in metadata
                if 'metadata' not in mapped:
                    mapped['metadata'] = {}
                mapped['metadata'][key] = value
        
        return mapped
    
    def _normalize_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize values based on field type."""
        normalized = data.copy()
        
        for key, value in normalized.items():
            # Normalize amounts
            if key in ['subtotal', 'tax_total', 'shipping_total', 'discount_total', 'total_amount']:
                normalized[key] = self._normalize_amount(value)
            
            # Normalize dates
            elif key in ['document_date', 'due_date', 'delivery_date']:
                normalized[key] = self._normalize_date(value)
            
            # Normalize vendor name
            elif key == 'vendor' and isinstance(value, dict):
                if 'name' in value:
                    value['name'] = self._normalize_vendor_name(value['name'])
            
            # Normalize tax ID
            elif key == 'tax_id':
                normalized[key] = self._normalize_tax_id(value)
        
        return normalized
    
    def _normalize_amount(self, value: Any) -> Optional[float]:
        """Normalize amount to float."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,€£\s]', '', value)
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
    
    def _normalize_date(self, value: Any) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format."""
        if value is None:
            return None
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            formats = [
                '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
                '%Y%m%d', '%b %d, %Y', '%d %b %Y',
                '%B %d, %Y', '%d %B %Y'
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date().isoformat()
                except ValueError:
                    continue
        return None
    
    def _normalize_vendor_name(self, name: str) -> str:
        """Normalize vendor name."""
        if not name:
            return ''
        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name).strip()
        # Standardize common suffixes
        name = re.sub(r'\s+Inc\.?$', ' Inc', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+LLC\.?$', ' LLC', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+Corp\.?$', ' Corp', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+Ltd\.?$', ' Ltd', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+Co\.?$', ' Co', name, flags=re.IGNORECASE)
        return name
    
    def _normalize_tax_id(self, tax_id: str) -> str:
        """Normalize tax ID."""
        if not tax_id:
            return ''
        # Remove spaces and dashes
        cleaned = re.sub(r'[\s\-]', '', tax_id)
        return cleaned
    
    def _extract_from_extraction(
        self,
        data: Dict[str, Any],
        extraction_result: Any
    ) -> Dict[str, Any]:
        """Extract additional data from extraction result."""
        extracted = data.copy()
        
        # Try to get structured extraction
        if hasattr(extraction_result, 'extracted_fields'):
            fields = extraction_result.extracted_fields
            
            # Extract vendor from fields
            if 'vendor_name' in fields and 'vendor' not in extracted:
                vendor = extracted.get('vendor', {})
                vendor['name'] = fields['vendor_name']
                extracted['vendor'] = vendor
            
            # Extract total from fields
            if 'total_amount' in fields and 'total_amount' not in extracted:
                extracted['total_amount'] = self._normalize_amount(fields['total_amount'])
            
            # Extract date from fields
            if 'date' in fields and 'document_date' not in extracted:
                extracted['document_date'] = self._normalize_date(fields['date'])
        
        return extracted
    
    def _structure_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Structure data into proper format."""
        structured = data.copy()
        
        # Ensure vendor object
        if 'vendor' not in structured or not isinstance(structured['vendor'], dict):
            structured['vendor'] = {}
        
        # Ensure buyer object
        if 'buyer' not in structured or not isinstance(structured['buyer'], dict):
            structured['buyer'] = {}
        
        # Ensure line_items is a list
        if 'line_items' not in structured or not isinstance(structured['line_items'], list):
            structured['line_items'] = []
        
        return structured
