import io
import re
from pathlib import Path
from typing import List, Tuple
import matplotlib.pyplot as plt
from matplotlib import mathtext
from PIL import Image
from app.config import settings
from app.utils.logger import logger

class LaTeXHandler:
    
    @staticmethod
    def extract_equations(content: str) -> List[Tuple[str, str, int]]:
        """
        Extract LaTeX equations from markdown content
        Returns list of (equation, mode, position) tuples
        mode: 'display' for $$...$$ or 'inline' for $...$
        """
        equations = []
        
        # Find display equations ($$...$$)
        display_pattern = r'\$\$(.*?)\$\$'
        content_without_display = content
        for match in re.finditer(display_pattern, content, re.DOTALL):
            equations.append((match.group(1).strip(), 'display', match.start()))
            content_without_display = content_without_display.replace(match.group(0), '')
        
        # Find inline equations ($...$) but not already captured
        inline_pattern = r'\$([^\$]+?)\$'
        for match in re.finditer(inline_pattern, content_without_display):
            equations.append((match.group(1).strip(), 'inline', match.start()))
        
        return equations
    
    @staticmethod
    def latex_to_image(latex: str, filename: str, display_mode: bool = True) -> Path:
        """
        Convert LaTeX equation to image
        """
        try:
            # Set up the figure
            fig = plt.figure(figsize=(10, 2) if display_mode else (6, 1))
            fig.patch.set_facecolor('white')
            
            # Render the equation
            text = f"${latex}$"
            
            plt.text(0.5, 0.5, text,
                    size=18 if display_mode else 14,
                    ha='center', va='center',
                    color='black')
            
            plt.axis('off')
            plt.tight_layout(pad=0.3)
            
            # Save image
            image_path = settings.IMAGES_DIR / filename
            plt.savefig(image_path, dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
            logger.debug(f"Generated LaTeX image: {filename}")
            return image_path
            
        except Exception as e:
            logger.error(f"Error generating LaTeX image: {str(e)}")
            raise
    
    @staticmethod
    def process_article_equations(content: str, article_id: str) -> Tuple[str, int]:
        """
        Process all equations in article and replace with image references
        Returns (modified_content, equation_count)
        """
        equations = LaTeXHandler.extract_equations(content)
        
        if not equations:
            return content, 0
        
        modified_content = content
        equation_images = []
        
        for idx, (equation, mode, position) in enumerate(equations):
            try:
                filename = f"eq_{article_id}_{idx}.png"
                image_path = LaTeXHandler.latex_to_image(
                    equation, 
                    filename, 
                    display_mode=(mode == 'display')
                )
                
                # Create markdown image reference
                image_ref = f"\n\n![Equation {idx + 1}](/static/images/{filename})\n\n"
                
                # Replace equation with image reference
                if mode == 'display':
                    pattern = re.escape(f"$${equation}$$")
                else:
                    pattern = re.escape(f"${equation}$")
                
                modified_content = re.sub(pattern, image_ref, modified_content, count=1)
                equation_images.append(filename)
                
            except Exception as e:
                logger.error(f"Failed to process equation {idx}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(equation_images)} equations for article {article_id}")
        return modified_content, len(equation_images)

latex_handler = LaTeXHandler()

