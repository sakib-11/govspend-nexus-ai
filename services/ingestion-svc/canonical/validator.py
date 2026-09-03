"""Validation module for canonical data."""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import ValidationError
import re
from datetime import datetime, date
from decimal import Decimal
import logging

from ..models.canonical import CanonicalTransaction, Vendor, Buyer, LineItem, TransactionStatus

logger = logging.getLogger(__name__)

class TransactionValidator:
    """Validate raw data against canonical schema."""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self, raw_data: Dict[str, Any]) -> Tuple[Optional[CanonicalTransaction], List[str], List[str]]:
        """
        Validate raw data and return canonical transaction.
        
        Returns:
            Tuple of (canonical_transaction, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        try:
            # Step 1: Clean and normalize data
            cleaned_data = self._clean_data(raw_data)
            
            # Step 2: Validate required fields
            self._validate_required_fields(cleaned_data)
            
            # Step 3: Validate data types and formats
            self._validate_data_types(cleaned_data)
            
            # Step 4: Validate business rules
            self._validate_business_rules(cleaned_data)
            
            # Step 5: Create canonical transaction
            if self.errors and self.strict_mode:
                raise ValueError(f"Validation failed: {', '.join(self.errors)}")
            
            transaction = self._create_canonical_transaction(cleaned_data)
            
            # Add validation metadata
            transaction.validation_errors = self.errors
            transaction.validation_warnings = self.warnings
            transaction.is_valid = len(self.errors) == 0
            
            if transaction.is_valid:
                transaction.status = TransactionStatus.VALIDATED
            
            return transaction, self.errors, self.warnings
            
        except ValidationError as e:
            self.errors.extend([f"{err['loc']}: {err['msg']}" for err in e.errors()])
            return None, self.errors, self.warnings
        except Exception as e:
            self.errors.append(f"Validation error: {str(e)}")
            return None, self.errors, self.warnings
    
    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize raw data."""
        cleaned = {}
        
        for key, value in data.items():
            # Clean strings
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
            
            # Convert date strings
            if key in ['document_date', 'due_date', 'delivery_date']:
                value = self._parse_date(value)
            
            # Convert amounts
            if key in ['subtotal', 'tax_total', 'shipping_total', 'discount_total', 'total_amount']:
                value = self._parse_amount(value)
            
            cleaned[key] = value
        
        return cleaned
    
    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            formats = [
                '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
                '%Y%m%d', '%b %d, %Y', '%d %b %Y',
                '%B %d, %Y', '%d %B %Y', '%m-%d-%Y',
                '%d-%m-%Y', '%Y-%m-%dT%H:%M:%S'
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None
    
    def _parse_amount(self, value: Any) -> Optional[Decimal]:
        """Parse amount from various formats."""
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,€£\s]', '', value)
            if cleaned.startswith('-'):
                cleaned = cleaned[1:]
                try:
                    return -Decimal(cleaned)
                except:
                    return None
            try:
                return Decimal(cleaned)
            except:
                return None
        return None
    
    def _validate_required_fields(self, data: Dict[str, Any]):
        """Validate required fields."""
        required_fields = {
            'document_number': 'Document number is required',
            'document_date': 'Document date is required',
            'vendor': 'Vendor information is required',
            'buyer': 'Buyer information is required',
            'total_amount': 'Total amount is required',
        }
        
        for field, message in required_fields.items():
            if field not in data or data[field] is None:
                self.errors.append(message)
        
        # Validate nested vendor fields
        if 'vendor' in data and data['vendor']:
            vendor = data['vendor']
            if not vendor.get('name'):
                self.errors.append('Vendor name is required')
        
        if 'buyer' in data and data['buyer']:
            buyer = data['buyer']
            if not buyer.get('name'):
                self.errors.append('Buyer name is required')
    
    def _validate_data_types(self, data: Dict[str, Any]):
        """Validate data types and formats."""
        # Validate amounts
        amount_fields = ['subtotal', 'tax_total', 'shipping_total', 'discount_total', 'total_amount']
        for field in amount_fields:
            if field in data and data[field] is not None:
                if not isinstance(data[field], Decimal):
                    self.errors.append(f"{field} must be a valid number")
                elif data[field] < 0:
                    self.errors.append(f"{field} cannot be negative")
        
        # Validate dates
        date_fields = ['document_date', 'due_date', 'delivery_date']
        for field in date_fields:
            if field in data and data[field] is not None:
                if not isinstance(data[field], date):
                    self.errors.append(f"{field} must be a valid date")
        
        # Validate document number format
        if 'document_number' in data and data['document_number']:
            doc_num = data['document_number']
            if not re.search(r'[A-Za-z0-9]', doc_num):
                self.warnings.append("Document number should contain alphanumeric characters")
            if len(doc_num) < 2:
                self.errors.append("Document number is too short")
    
    def _validate_business_rules(self, data: Dict[str, Any]):
        """Validate business rules."""
        # Validate date logic
        if 'document_date' in data and 'due_date' in data:
            if data['document_date'] and data['due_date']:
                if data['due_date'] < data['document_date']:
                    self.warnings.append("Due date is before document date")
        
        # Validate total matches subtotal + tax
        if all(k in data for k in ['subtotal', 'tax_total', 'total_amount']):
            if data['subtotal'] is not None and data['tax_total'] is not None and data['total_amount'] is not None:
                calculated = data['subtotal'] + data['tax_total']
                shipping = data.get('shipping_total', Decimal('0'))
                discount = data.get('discount_total', Decimal('0'))
                calculated = calculated + shipping - discount
                
                if abs(data['total_amount'] - calculated) > Decimal('0.01'):
                    self.warnings.append(
                        f"Total amount ({data['total_amount']}) differs from calculated total ({calculated})"
                    )
        
        # Validate line items
        if 'line_items' in data and data['line_items']:
            self._validate_line_items(data['line_items'])
    
    def _validate_line_items(self, line_items: List[Dict[str, Any]]):
        """Validate line items."""
        for i, item in enumerate(line_items):
            if not item.get('description'):
                self.errors.append(f"Line item {i+1}: Description is required")
            
            if 'quantity' in item and item['quantity'] is not None:
                try:
                    quantity = Decimal(str(item['quantity']))
                    if quantity < 0:
                        self.errors.append(f"Line item {i+1}: Quantity cannot be negative")
                except:
                    self.errors.append(f"Line item {i+1}: Invalid quantity")
            
            if 'unit_price' in item and item['unit_price'] is not None:
                try:
                    unit_price = Decimal(str(item['unit_price']))
                    if unit_price < 0:
                        self.errors.append(f"Line item {i+1}: Unit price cannot be negative")
                except:
                    self.errors.append(f"Line item {i+1}: Invalid unit price")
    
    def _create_canonical_transaction(self, data: Dict[str, Any]) -> CanonicalTransaction:
        """Create canonical transaction from cleaned data."""
        # Build Vendor object
        vendor_data = data.get('vendor', {})
        if isinstance(vendor_data, dict):
            vendor = Vendor(
                name=vendor_data.get('name', 'Unknown Vendor'),
                tax_id=vendor_data.get('tax_id'),
                address=vendor_data.get('address'),
                city=vendor_data.get('city'),
                state=vendor_data.get('state'),
                country=vendor_data.get('country'),
                postal_code=vendor_data.get('postal_code'),
                phone=vendor_data.get('phone'),
                email=vendor_data.get('email'),
                website=vendor_data.get('website')
            )
        else:
            vendor = Vendor(name='Unknown Vendor')
        
        # Build Buyer object
        buyer_data = data.get('buyer', {})
        if isinstance(buyer_data, dict):
            buyer = Buyer(
                name=buyer_data.get('name', 'Unknown Buyer'),
                department=buyer_data.get('department'),
                address=buyer_data.get('address'),
                city=buyer_data.get('city'),
                state=buyer_data.get('state'),
                country=buyer_data.get('country'),
                postal_code=buyer_data.get('postal_code'),
                contact_person=buyer_data.get('contact_person'),
                contact_email=buyer_data.get('contact_email'),
                contact_phone=buyer_data.get('contact_phone')
            )
        else:
            buyer = Buyer(name='Unknown Buyer')
        
        # Build Line Items
        line_items = []
        for item_data in data.get('line_items', []):
            try:
                line_item = LineItem(
                    line_number=item_data.get('line_number'),
                    description=item_data.get('description', 'Unknown item'),
                    quantity=Decimal(str(item_data.get('quantity', 1))),
                    unit_price=Decimal(str(item_data.get('unit_price', 0))),
                    total=item_data.get('total'),
                    tax_rate=item_data.get('tax_rate'),
                    tax_amount=item_data.get('tax_amount'),
                    discount_rate=item_data.get('discount_rate'),
                    discount_amount=item_data.get('discount_amount'),
                    product_code=item_data.get('product_code'),
                    unit_of_measure=item_data.get('unit_of_measure')
                )
                line_items.append(line_item)
            except Exception as e:
                self.warnings.append(f"Failed to parse line item: {str(e)}")
        
        # Create transaction
        transaction = CanonicalTransaction(
            source_id=data.get('source_id', 'unknown'),
            transaction_type=data.get('transaction_type', TransactionType.INVOICE),
            document_number=data.get('document_number', 'UNKNOWN'),
            purchase_order=data.get('purchase_order'),
            reference_number=data.get('reference_number'),
            document_date=data.get('document_date', date.today()),
            due_date=data.get('due_date'),
            delivery_date=data.get('delivery_date'),
            vendor=vendor,
            buyer=buyer,
            subtotal=data.get('subtotal'),
            tax_total=data.get('tax_total'),
            shipping_total=data.get('shipping_total'),
            discount_total=data.get('discount_total'),
            total_amount=data.get('total_amount', Decimal('0')),
            currency=data.get('currency', CurrencyCode.USD),
            line_items=line_items,
            payment_terms=data.get('payment_terms'),
            payment_method=data.get('payment_method'),
            notes=data.get('notes'),
            tags=data.get('tags', []),
            metadata=data.get('metadata', {})
        )
        
        return transaction

