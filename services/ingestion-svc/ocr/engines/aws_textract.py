"""AWS Textract OCR engine implementation."""

import boto3
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import json
import base64

from ..core import BaseOCREngine, OCRResult

logger = logging.getLogger(__name__)

class AWSTextractEngine(BaseOCREngine):
    """AWS Textract OCR engine with advanced document analysis."""
    
    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: str = "us-east-1",
        use_async: bool = False,
        bucket_name: Optional[str] = None,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region
        self.use_async = use_async
        self.bucket_name = bucket_name
        
        # Initialize Textract client
        self._client = None
        self._initialized = False
    
    def _get_client(self):
        """Get or create Textract client."""
        if not self._initialized:
            try:
                if self.access_key_id and self.secret_access_key:
                    self._client = boto3.client(
                        'textract',
                        aws_access_key_id=self.access_key_id,
                        aws_secret_access_key=self.secret_access_key,
                        region_name=self.region
                    )
                else:
                    # Use default credentials from environment
                    self._client = boto3.client('textract', region_name=self.region)
                
                self._initialized = True
                logger.info("AWS Textract client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize AWS Textract: {str(e)}")
                raise
        
        return self._client
    
    async def process(
        self,
        file_path: Path,
        content_type: str = "application/pdf",
        options: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Process document with AWS Textract."""
        options = options or {}
        client = self._get_client()
        
        try:
            # Read file bytes
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            # Determine content type for Textract
            is_pdf = file_path.suffix.lower() == ".pdf"
            
            if self.use_async and self.bucket_name:
                # Async processing for large documents
                result = await self._process_async(client, file_bytes, is_pdf)
            else:
                # Synchronous processing
                result = await self._process_sync(client, file_bytes, is_pdf)
            
            # Extract structured fields
            extracted_fields = self._extract_fields(result)
            
            return OCRResult(
                raw_text=result.get("text", ""),
                confidence=result.get("confidence", 0.0),
                extracted_fields=extracted_fields,
                bounding_boxes=result.get("bounding_boxes"),
                page_count=result.get("page_count", 1),
                warnings=[],
                metadata={
                    "engine": "aws_textract",
                    "document_type": result.get("document_type", "unknown"),
                    "async_processing": self.use_async,
                    "has_tables": bool(extracted_fields.get("tables"))
                }
            )
            
        except Exception as e:
            logger.error(f"AWS Textract processing failed: {str(e)}")
            raise
    
    async def _process_sync(self, client, file_bytes: bytes, is_pdf: bool) -> Dict[str, Any]:
        """Synchronous document processing."""
        if is_pdf:
            # Process PDF
            response = client.analyze_document(
                Document={'Bytes': file_bytes},
                FeatureTypes=['TABLES', 'FORMS']
            )
        else:
            # Process image
            response = client.analyze_document(
                Document={'Bytes': file_bytes},
                FeatureTypes=['TABLES', 'FORMS']
            )
        
        return self._parse_textract_response(response)
    
    async def _process_async(self, client, file_bytes: bytes, is_pdf: bool) -> Dict[str, Any]:
        """Asynchronous document processing for large files."""
        # Upload to S3 bucket
        import uuid
        import boto3
        
        s3 = boto3.client('s3', region_name=self.region)
        object_key = f"ocr-uploads/{uuid.uuid4()}.{file_path.suffix[1:]}"
        
        s3.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=file_bytes
        )
        
        # Start async job
        if is_pdf:
            response = client.start_document_analysis(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.bucket_name,
                        'Name': object_key
                    }
                },
                FeatureTypes=['TABLES', 'FORMS']
            )
        else:
            response = client.start_document_analysis(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.bucket_name,
                        'Name': object_key
                    }
                },
                FeatureTypes=['TABLES', 'FORMS']
            )
        
        job_id = response['JobId']
        
        # Poll for completion
        import time
        max_attempts = 30
        for attempt in range(max_attempts):
            status_response = client.get_document_analysis(JobId=job_id)
            status = status_response['JobStatus']
            
            if status == 'SUCCEEDED':
                # Get full result
                final_response = client.get_document_analysis(JobId=job_id)
                return self._parse_textract_response(final_response)
            elif status == 'FAILED':
                raise RuntimeError(f"Textract job failed: {status_response.get('StatusMessage', 'Unknown error')}")
            
            time.sleep(2)
        
        raise TimeoutError(f"Textract job {job_id} timed out")
    
    def _parse_textract_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Textract response into structured data."""
        text_lines = []
        confidence_scores = []
        bounding_boxes = []
        form_data = {}
        tables = []
        
        # Process blocks
        for block in response.get('Blocks', []):
            block_type = block.get('BlockType')
            
            if block_type == 'LINE':
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0)
                text_lines.append(text)
                confidence_scores.append(confidence)
                
                # Get bounding box
                geometry = block.get('Geometry', {})
                if geometry:
                    bounding_boxes.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': geometry.get('BoundingBox', {})
                    })
            
            elif block_type == 'KEY_VALUE_SET':
                # Extract form fields (key-value pairs)
                if block.get('EntityTypes') == ['KEY']:
                    # This is a key
                    key = self._extract_text_from_block(response, block.get('Relationships', []))
                    value_block = self._find_value_block(response, block)
                    if key and value_block:
                        form_data[key] = value_block
            
            elif block_type == 'TABLE':
                # Extract tables
                table_data = self._extract_table(response, block)
                if table_data:
                    tables.append(table_data)
        
        # Calculate overall confidence
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        return {
            "text": "\n".join(text_lines),
            "confidence": avg_confidence / 100.0,
            "bounding_boxes": bounding_boxes,
            "page_count": len(response.get('Blocks', [])),
            "document_type": "pdf" if any(b.get('Page', 0) > 0 for b in response.get('Blocks', [])) else "image",
            "fields": form_data,
            "tables": tables
        }
    
    def _extract_text_from_block(self, response: Dict, relationships: List[Dict]) -> str:
        """Extract text from a block's relationships."""
        texts = []
        for rel in relationships:
            if rel.get('Type') == 'CHILD':
                for child_id in rel.get('Ids', []):
                    for block in response.get('Blocks', []):
                        if block.get('Id') == child_id:
                            if block.get('BlockType') == 'WORD':
                                texts.append(block.get('Text', ''))
                            elif block.get('BlockType') == 'SELECTION_ELEMENT':
                                texts.append(block.get('SelectionStatus', ''))
        return " ".join(texts)
    
    def _find_value_block(self, response: Dict, key_block: Dict) -> str:
        """Find the value block associated with a key block."""
        for rel in key_block.get('Relationships', []):
            if rel.get('Type') == 'VALUE':
                for value_id in rel.get('Ids', []):
                    for block in response.get('Blocks', []):
                        if block.get('Id') == value_id:
                            return self._extract_text_from_block(response, block.get('Relationships', []))
        return ""
    
    def _extract_table(self, response: Dict, table_block: Dict) -> List[List[str]]:
        """Extract table data from a table block."""
        table_data = []
        cells_by_row = {}
        
        # Get all cells in the table
        for rel in table_block.get('Relationships', []):
            if rel.get('Type') == 'CHILD':
                for cell_id in rel.get('Ids', []):
                    for block in response.get('Blocks', []):
                        if block.get('Id') == cell_id:
                            row = block.get('RowIndex', 0)
                            col = block.get('ColumnIndex', 0)
                            text = self._extract_text_from_block(response, block.get('Relationships', []))
                            
                            if row not in cells_by_row:
                                cells_by_row[row] = {}
                            cells_by_row[row][col] = text
        
        # Convert to 2D array
        for row in sorted(cells_by_row.keys()):
            row_data = []
            for col in sorted(cells_by_row[row].keys()):
                row_data.append(cells_by_row[row][col])
            table_data.append(row_data)
        
        return table_data
    
    def _extract_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured fields from Textract result."""
        fields = {}
        
        # Add form fields
        if "fields" in result:
            fields.update(result["fields"])
        
        # Add tables
        if "tables" in result:
            fields["tables"] = result["tables"]
        
        return fields
    
    async def health_check(self) -> bool:
        """Check if AWS Textract is accessible."""
        try:
            client = self._get_client()
            # Simple API call to check connectivity
            client.detect_document_text(
                Document={'Bytes': b'test'}
            )
            return True
        except Exception as e:
            logger.error(f"AWS Textract health check failed: {str(e)}")
            return False
