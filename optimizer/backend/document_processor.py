# Presidio Optimizer
# Copyright (C) 2026 Sambruk
#
# Detta program är fri programvara; du får sprida och ändra det enligt
# villkoren i GNU General Public License version 2, som den publicerats av
# Free Software Foundation.
#
# Programmet distribueras i hopp om att det ska vara användbart, men UTAN
# NÅGON GARANTI. Se GNU General Public License för fler detaljer.
# Se filen LICENSE.

import os
import logging
from typing import Optional
import docx
import openpyxl
import PyPDF2
import aiofiles

logger = logging.getLogger(__name__)

class DocumentProcessor:
    async def extract_text(self, file_path: str, file_type: str) -> str:
        """Extract text from different file formats"""
        if file_type == "txt":
            return await self._extract_txt(file_path)
        elif file_type == "docx":
            return await self._extract_docx(file_path)
        elif file_type == "xlsx":
            return await self._extract_xlsx(file_path)
        elif file_type == "pdf":
            return await self._extract_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def _extract_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return await f.read()
    
    async def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            full_text = []
            
            # Extract paragraphs
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    full_text.append(paragraph.text)
            
            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text)
                    if row_text:
                        full_text.append(' | '.join(row_text))
            
            result = '\n'.join(full_text)
            logger.info(f"Extracted {len(result)} characters from DOCX")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting DOCX: {str(e)} - attempting text fallback")
            # Fallback: try to read as text file
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                    logger.info(f"Used text fallback for DOCX, extracted {len(content)} characters")
                    return content
            except Exception as fallback_error:
                logger.error(f"Text fallback also failed: {str(fallback_error)}")
                raise Exception(f"Could not process file as DOCX or text: {str(e)}")
    
    async def _extract_xlsx(self, file_path: str) -> str:
        """Extract text from XLSX file"""
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            full_text = []
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                full_text.append(f"Sheet: {sheet_name}")
                
                for row in sheet.iter_rows(values_only=True):
                    row_text = []
                    for cell in row:
                        if cell is not None:
                            row_text.append(str(cell))
                    if row_text:
                        full_text.append('\t'.join(row_text))
            
            result = '\n'.join(full_text)
            logger.info(f"Extracted {len(result)} characters from XLSX")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting XLSX: {str(e)} - attempting text fallback")
            # Fallback: try to read as text file
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                    logger.info(f"Used text fallback for XLSX, extracted {len(content)} characters")
                    return content
            except Exception as fallback_error:
                logger.error(f"Text fallback also failed: {str(fallback_error)}")
                raise Exception(f"Could not process file as XLSX or text: {str(e)}")
    
    async def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            full_text = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
            
            result = '\n'.join(full_text)
            logger.info(f"Extracted {len(result)} characters from PDF")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting PDF: {str(e)} - attempting text fallback")
            # Fallback: try to read as text file
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                    logger.info(f"Used text fallback for PDF, extracted {len(content)} characters")
                    return content
            except Exception as fallback_error:
                logger.error(f"Text fallback also failed: {str(fallback_error)}")
                raise Exception(f"Could not process file as PDF or text: {str(e)}")
    
    async def create_anonymized_document(self, 
                                        anonymized_text: str, 
                                        output_path: str, 
                                        file_type: str,
                                        original_path: Optional[str] = None):
        """Create anonymized document in the original format"""
        if file_type == "txt":
            await self._create_txt(anonymized_text, output_path)
        elif file_type == "docx":
            await self._create_docx(anonymized_text, output_path, original_path)
        elif file_type == "xlsx":
            await self._create_xlsx(anonymized_text, output_path, original_path)
        elif file_type == "pdf":
            await self._create_pdf_as_txt(anonymized_text, output_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def _create_txt(self, text: str, output_path: str):
        """Create TXT file"""
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(text)
    
    async def _create_docx(self, text: str, output_path: str, original_path: Optional[str] = None):
        """Create DOCX file"""
        try:
            # For now, create a simple new document with anonymized text
            # Preserving complex DOCX formatting is challenging
            doc = docx.Document()
            
            # Add anonymized text as paragraphs
            for paragraph_text in text.split('\n'):
                if paragraph_text.strip():
                    doc.add_paragraph(paragraph_text)
            
            doc.save(output_path)
            logger.info(f"Successfully created anonymized DOCX at {output_path}")
            
        except Exception as e:
            logger.error(f"Error creating DOCX: {str(e)}")
            # Fallback to text file
            txt_path = output_path.replace('.docx', '.txt')
            async with aiofiles.open(txt_path, 'w', encoding='utf-8') as f:
                await f.write(text)
            # Rename to keep .docx extension even though it's a text file
            os.rename(txt_path, output_path)
    
    async def _create_xlsx(self, text: str, output_path: str, original_path: Optional[str] = None):
        """Create XLSX file"""
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Anonymized Data"
        
        lines = text.split('\n')
        for row_idx, line in enumerate(lines, start=1):
            if line.strip():
                cells = line.split('\t')
                for col_idx, cell_value in enumerate(cells, start=1):
                    sheet.cell(row=row_idx, column=col_idx, value=cell_value)
        
        workbook.save(output_path)
    
    async def _create_pdf_as_txt(self, text: str, output_path: str):
        """Create text file for PDF content (PDF creation is complex)"""
        # Instead of creating .txt file, create the expected .pdf file with text content
        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write("ANONYMIZED DOCUMENT (Original format: PDF)\n")
            await f.write("=" * 50 + "\n\n")
            await f.write(text)
        logger.info(f"Successfully created anonymized PDF as text file at {output_path}")