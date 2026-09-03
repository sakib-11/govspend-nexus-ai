"""Canonicalization pipeline for transforming raw data to canonical format."""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
import json

from .validator import TransactionValidator
from .transformers import DataTransformer
from ..models.canonical import CanonicalTransaction, TransactionStatus
from ..models.extraction import ExtractionResult

logger = logging.getLogger(__name__)

class Canonicalizer:
    """Canonicalization pipeline."""
    
    def __init__(self, strict_mode: bool = True):
        self.validator = TransactionValidator(strict_mode=strict_mode)
        self.transformer = DataTransformer()
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
    
    async def canonicalize(
        self,
        raw_data: Dict[str, Any],
        source_id: str,
        extraction_result: Optional[ExtractionResult] = None
    ) -> Dict[str, Any]:
        """
        Transform raw data to canonical format.
        
        Args:
            raw_data: Raw extracted data
            source_id: Source upload ID
            extraction_result: Optional extraction result for additional context
            
        Returns:
            Dictionary with canonicalization results
        """
        start_time = datetime.now()
        self.stats['total_processed'] += 1
        
        try:
            logger.info(f"Starting canonicalization for source: {source_id}")
            
            # Step 1: Add source ID
            raw_data['source_id'] = source_id
            
            # Step 2: Transform raw data
            transformed_data = await self.transformer.transform(
                raw_data=raw_data,
                extraction_result=extraction_result
            )
            
            # Step 3: Validate and create canonical transaction
            transaction, errors, warnings = self.validator.validate(transformed_data)
            
            # Step 4: Prepare response
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if transaction and transaction.is_valid:
                self.stats['successful'] += 1
                return {
                    'success': True,
                    'transaction': transaction.to_dict(),
                    'validation': {
                        'is_valid': True,
                        'errors': [],
                        'warnings': warnings
                    },
                    'processing_time_seconds': processing_time,
                    'status': 'canonicalized',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.stats['failed'] += 1
                error_messages = errors or ['Validation failed']
                self.stats['errors'].extend(error_messages)
                
                return {
                    'success': False,
                    'transaction': transaction.to_dict() if transaction else None,
                    'validation': {
                        'is_valid': False,
                        'errors': error_messages,
                        'warnings': warnings
                    },
                    'processing_time_seconds': processing_time,
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.stats['failed'] += 1
            error_msg = str(e)
            self.stats['errors'].append(error_msg)
            logger.error(f"Canonicalization failed: {error_msg}", exc_info=True)
            
            return {
                'success': False,
                'transaction': None,
                'validation': {
                    'is_valid': False,
                    'errors': [error_msg],
                    'warnings': []
                },
                'processing_time_seconds': (datetime.now() - start_time).total_seconds(),
                'status': 'error',
                'timestamp': datetime.now().isoformat()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get canonicalization statistics."""
        return {
            **self.stats,
            'success_rate': self.stats['successful'] / max(self.stats['total_processed'], 1)
        }
    
    def validate_transaction(self, transaction: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a canonical transaction."""
        try:
            # Try to create CanonicalTransaction from dict
            canonical = CanonicalTransaction(**transaction)
            return True, []
        except Exception as e:
            return False, [str(e)]

