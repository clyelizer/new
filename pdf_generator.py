from reportlab.lib import colors
from reportlab.lib.pagesizes import A4  # Changed to A4 for more space, can be letter if preferred
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import cm # Using cm for easier layout from image
import os # For checking stamp path if used

def generate_bulletin_pdf(output_path, student_data, grades_part1, grades_part2, summary_data):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Helper function to create styled paragraphs
    def create_paragraph(text, style_name, alignment=TA_LEFT, space_after=0, space_before=0, font_size=None, leading=None, text_color=colors.black):
        style = ParagraphStyle(name=f'Custom{style_name}-{text[:10]}', parent=styles[style_name]) # Unique name
        style.alignment = alignment
        style.spaceAfter = space_after * cm
        style.spaceBefore = space_before * cm
        style.textColor = text_color
        if font_size:
            style.fontSize = font_size
        if leading:
            style.leading = leading
        return Paragraph(text, style)

    # School Header
    elements.append(create_paragraph("Ministère de l'Education Nationale", 'Normal', alignment=TA_LEFT, font_size=10))
    elements.append(create_paragraph("***************************", 'Normal', alignment=TA_LEFT, font_size=8, space_after=0.1))
    elements.append(create_paragraph("Académie d'Enseignement de Ségou", 'Normal', alignment=TA_LEFT, font_size=10))
    elements.append(create_paragraph("***************************", 'Normal', alignment=TA_LEFT, font_size=8, space_after=0.2))
    
    header_table_data = [
        [create_paragraph(f"<b>Lycée {student_data.get('school_name', 'Michel ALLAIRE')} de Ségou</b> BP : {student_data.get('school_bp', '580')} TEL: {student_data.get('school_tel', '21-32-11-20')}", 'Normal', font_size=10),
         create_paragraph("République du Mali", 'Normal', alignment=TA_RIGHT, font_size=10)],
        [create_paragraph(f"E-mail: {student_data.get('school_email', 'michelallaire2007@yahoo.fr')} / {student_data.get('school_tel_alt', '79 07 03 60')}", 'Normal', font_size=10),
         create_paragraph("Un Peuple-Un But-Une Foi", 'Normal', alignment=TA_RIGHT, font_size=9)],
        ['', create_paragraph("***************************", 'Normal', alignment=TA_RIGHT, font_size=8)]
    ]
    header_table = Table(header_table_data, colWidths=[12*cm, 6*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0), # Added to minimize spacing
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*cm))

    # Student and Class Info
    student_name_str = student_data.get('student_name', 'NOM PRENOM DE L\'ELEVE').upper()
    student_info_line1 = f"<b>{student_data.get('academic_period', '2ème Période 2022-2023')}</b>"
    student_info_line2 = f"<b>{student_name_str}</b>"
    student_info_line3 = f"<b>{student_data.get('class_name', '12ème TSE')}</b>"

    # Table for Student Info layout
    # Row 1: academic_period (left), student_name (center), class_name (right)
    info_layout_table_data = [
        [create_paragraph(student_info_line1, 'Normal', alignment=TA_LEFT, font_size=11),
         create_paragraph(student_info_line2, 'Normal', alignment=TA_CENTER, font_size=16), # Larger font for name
         create_paragraph(student_info_line3, 'Normal', alignment=TA_RIGHT, font_size=11)]
    ]
    info_layout_table = Table(info_layout_table_data, colWidths=[6*cm, 6*cm, 6*cm])
    info_layout_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(info_layout_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Grades Table Header & Function
    col_widths_grades = [4.6*cm, 1.2*cm, 1.7*cm, 1.7*cm, 1.2*cm, 2.4*cm, 2.2*cm] # Adjusted widths
    
    def create_grades_table(grades_list): # Removed title argument
        header_texts = ['Matières', 'Moy,CL\nm', 'N, Compo\nn', 'M,G,\n(m+2n)/3', 'Coef,\nk', 'Moy Coef\n(m+2n)/3*k', 'Appr,']
        header_paragraphs = [create_paragraph(text, 'Normal', alignment=TA_CENTER, font_size=8, leading=9) for text in header_texts]
        table_data = [header_paragraphs]
        
        total_coef_part = 0
        total_moy_coef_part = 0.0

        for grade_item in grades_list:
            m = float(grade_item.get('moy_cl', 0))
            n = float(grade_item.get('n_compo', 0))
            k = int(grade_item.get('coef', 0))
            
            mg = (m + 2*n) / 3.0 if k > 0 else 0.0
            moy_coef = mg * k
            
            total_coef_part += k
            total_moy_coef_part += moy_coef
            
            table_data.append([
                create_paragraph(str(grade_item.get('subject', '')), 'Normal', font_size=8, alignment=TA_LEFT),
                create_paragraph(f'{m:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER),
                create_paragraph(f'{n:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER),
                create_paragraph(f'{mg:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER),
                create_paragraph(str(k), 'Normal', font_size=8, alignment=TA_CENTER),
                create_paragraph(f'{moy_coef:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER),
                create_paragraph(str(grade_item.get('appreciation', '')), 'Normal', font_size=8, alignment=TA_CENTER),
            ])
        
        table = Table(table_data, colWidths=col_widths_grades, rowHeights=[1*cm] + [0.6*cm]*len(grades_list)) # Header height + row height
        style = TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), 
            ('LEFTPADDING', (0,1), (0,-1), 3), # Padding for subject content
            ('RIGHTPADDING', (0,1), (0,-1), 3),
        ])
        table.setStyle(style)
        elements.append(table)
        return total_coef_part, total_moy_coef_part

    # Part 1 Grades
    total_coef_p1, total_moy_coef_p1 = create_grades_table(grades_part1)
    
    # Part 1 Summary
    moy_partielle_p1 = (total_moy_coef_p1 / total_coef_p1) if total_coef_p1 > 0 else 0.0
    summary_p1_data = [
        [create_paragraph('<b>Total Partiel</b>', 'Normal', font_size=8, alignment=TA_LEFT), '', '', '', 
         create_paragraph(str(total_coef_p1), 'Normal', font_size=8, alignment=TA_CENTER), 
         create_paragraph(f'{total_moy_coef_p1:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER), 
         ''],
        [create_paragraph('<b>Moy.Partielle</b>', 'Normal', font_size=8, alignment=TA_LEFT), '', '', '', '', 
         create_paragraph(f'{moy_partielle_p1:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER), 
         create_paragraph(str(summary_data.get('appr_p1','')), 'Normal', font_size=8, alignment=TA_CENTER)]
    ]
    summary_p1_table = Table(summary_p1_data, colWidths=col_widths_grades, rowHeights=[0.6*cm, 0.6*cm])
    summary_p1_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (0,0), (3,0)), 
        ('SPAN', (0,1), (4,1)), 
        ('LEFTPADDING', (0,0), (0,-1), 3),
    ]))
    elements.append(summary_p1_table)
    elements.append(Spacer(1, 0.3*cm))

    # Part 2 Grades
    total_coef_p2, total_moy_coef_p2 = create_grades_table(grades_part2)

    # Part 2 Summary
    moy_partielle_p2 = (total_moy_coef_p2 / total_coef_p2) if total_coef_p2 > 0 else 0.0
    summary_p2_data = [
        [create_paragraph('<b>Total Partiel</b>', 'Normal', font_size=8, alignment=TA_LEFT), '', '', '', 
         create_paragraph(str(total_coef_p2), 'Normal', font_size=8, alignment=TA_CENTER), 
         create_paragraph(f'{total_moy_coef_p2:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER),
         ''],
        [create_paragraph('<b>Moy.Partielle</b>', 'Normal', font_size=8, alignment=TA_LEFT), '', '', '', '', 
         create_paragraph(f'{moy_partielle_p2:.2f}'.replace('.',','), 'Normal', font_size=8, alignment=TA_CENTER), 
         create_paragraph(str(summary_data.get('appr_p2','')), 'Normal', font_size=8, alignment=TA_CENTER)]
    ]
    summary_p2_table = Table(summary_p2_data, colWidths=col_widths_grades, rowHeights=[0.6*cm, 0.6*cm])
    summary_p2_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (0,0), (3,0)), 
        ('SPAN', (0,1), (4,1)),
        ('LEFTPADDING', (0,0), (0,-1), 3),
    ]))
    elements.append(summary_p2_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # Global Summary
    total_global_coef = total_coef_p1 + total_coef_p2
    total_global_moy_coef = total_moy_coef_p1 + total_moy_coef_p2
    moy_globale = (total_global_moy_coef / total_global_coef) if total_global_coef > 0 else 0.0
    
    total_global_row_data = [
        [create_paragraph('<b>Total Global</b>', 'Normal',font_size=9, alignment=TA_LEFT), '', '', '', 
         create_paragraph(str(total_global_coef), 'Normal', font_size=9, alignment=TA_CENTER), 
         create_paragraph(f'{total_global_moy_coef:.2f}'.replace('.',','), 'Normal', font_size=9, alignment=TA_CENTER), 
         create_paragraph(str(summary_data.get('appr_globale','')), 'Normal', font_size=9, alignment=TA_CENTER)]
    ]
    total_global_table_aligned = Table(total_global_row_data, colWidths=col_widths_grades, rowHeights=[0.7*cm])
    total_global_table_aligned.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('SPAN', (0,0), (3,0)), 
        ('LEFTPADDING', (0,0), (0,-1), 3),
    ]))
    elements.append(total_global_table_aligned)
    elements.append(Spacer(1, 0.5*cm)) # Increased space

    # Footer information: Rank, Date, Averages (using a single table for better alignment)
    # This part needs careful data from summary_data
    rang_text = f"Rang: {summary_data.get('rank', '1er')}"
    date_text = f"Ségou, le {summary_data.get('date_generated', '07/06/2023')}"
    moy_globale_text = f"Moy: {moy_globale:.2f} /20".replace('.',',')
    moy_premier_text = f"Moy, du 1er: {summary_data.get('rank_1_moy', '16,23/20')}"

    footer_line1_table_data = [
        [create_paragraph(rang_text, 'Normal', font_size=9, alignment=TA_LEFT),
         create_paragraph(date_text, 'Normal', font_size=9, alignment=TA_CENTER),
         create_paragraph(moy_globale_text, 'Normal', font_size=9, alignment=TA_RIGHT),
         create_paragraph(moy_premier_text, 'Normal', font_size=9, alignment=TA_RIGHT)]
    ]
    footer_line1_table = Table(footer_line1_table_data, colWidths=[4.5*cm, 5*cm, 4*cm, 4.5*cm]) # Adjusted
    footer_line1_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(footer_line1_table)
    elements.append(Spacer(1, 0.3*cm))

    moy_p1_overall_text = summary_data.get('moy_p1_overall', '16,51 /20')
    moy_p2_overall_text = summary_data.get('moy_p2_overall', '16,23 /20')
    moy_annuelle_text = summary_data.get('moy_annuelle', '16,37 /20')

    footer_data2 = [
        [create_paragraph(f"<b>Moy.1ère Période</b><br/>{moy_p1_overall_text}", 'Normal', font_size=9, alignment=TA_CENTER, leading=11), 
         create_paragraph(f"<b>Moy.2ème Période</b><br/>{moy_p2_overall_text}", 'Normal', font_size=9, alignment=TA_CENTER, leading=11), 
         create_paragraph(f"<b>Moyenne Annuelle</b><br/>{moy_annuelle_text}", 'Normal', font_size=9, alignment=TA_CENTER, leading=11)]
    ]
    footer_table2 = Table(footer_data2, colWidths=[6*cm, 6*cm, 6*cm], rowHeights=[1.2*cm]) # Set row height
    footer_table2.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(footer_table2)
    elements.append(Spacer(1, 1*cm))

    # Signatures and Stamp
    # Using a table for "Le Proviseur", "Tableau dExcellence" and "Signature du Parent"
    # This helps in positioning them correctly relative to each other and the stamp.

    proviseur_text = "Le Proviseur"
    tableau_excellence_text = "Tableau dExcellence"
    signature_parent_text = "Signature du Parent"

    # Attempt to place stamp - this is tricky with flowables. Absolute positioning might be better.
    # For now, let's assume it's part of the left column content or placed manually after generation.
    # If you have a stamp image:
    stamp_content = ""
    # try:
    #     stamp_path = student_data.get('school_stamp_path', None) # e.g. 'static/stamp.png'
    #     if stamp_path and os.path.exists(stamp_path):
    #         stamp_img = Image(stamp_path, width=2.5*cm, height=2.5*cm) # Adjust size
    #         stamp_content = stamp_img # This will place it as a flowable
    #     else:
    #         stamp_content = create_paragraph("(Sceau)", 'Normal', font_size=8, alignment=TA_CENTER)
    # except Exception as e:
    #     print(f"Error loading stamp: {e}")
    #     stamp_content = create_paragraph("(Erreur Sceau)", 'Normal', font_size=8, alignment=TA_CENTER)


    final_elements_data = [
        [create_paragraph(proviseur_text, 'Normal', font_size=10, alignment=TA_LEFT), '', ''],
        [stamp_content if stamp_content else create_paragraph("",'Normal'), '', ''], # Placeholder for stamp image or text
        [create_paragraph(tableau_excellence_text, 'Normal', font_size=10, alignment=TA_LEFT, space_before=0.5), 
         '', 
         create_paragraph(signature_parent_text, 'Normal', font_size=10, alignment=TA_RIGHT, space_before=0.5)]
    ]

    final_table = Table(final_elements_data, colWidths=[7*cm, 4*cm, 7*cm])
    final_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        # Span the stamp cell if it's just text, or adjust if it's an image
        ('SPAN', (0,1), (0,1)), # Span for stamp placeholder
    ]))

    elements.append(final_table)
    
    doc.build(elements)

# Example Usage (for testing purposes, adapt with real data from Flask app)
if __name__ == '__main__':
    # Ensure student_name, class_name are provided in student_data for the header
    dummy_student_data = {
        'school_name': 'Lycée Démo Ségou',
        'school_bp': 'BP TEST',
        'school_tel': '00-00-00-00',
        'school_email': 'demo@example.com',
        'school_tel_alt': '11-11-11-11',
        'academic_period': '1ère Période 2023-2024',
        'student_name': 'AÏSSATA DIALLO',      # Provide student's name
        'class_name': 'Terminale Sciences Sociales', # Provide student's class
        'school_stamp_path': None # Optional: 'path/to/your/stamp.png' 
    }
    dummy_grades_p1 = [
        {'subject': 'MATHS', 'moy_cl': 14, 'n_compo': 14.5, 'coef': 5, 'appreciation': 'Bien'},
        {'subject': 'PHYSIQUE', 'moy_cl': 16.5, 'n_compo': 16, 'coef': 3, 'appreciation': 'Tbien'},
        {'subject': 'CHIMIE', 'moy_cl': 17.5, 'n_compo': 18, 'coef': 3, 'appreciation': 'Tbien'},
        {'subject': 'GÉOLOGIE/BIO', 'moy_cl': 10, 'n_compo': 13, 'coef': 2, 'appreciation': 'Abien'},
        {'subject': 'PHILOSOPHIE', 'moy_cl': 14.75, 'n_compo': 15, 'coef': 2, 'appreciation': 'Bien'},
        {'subject': 'ANGLAIS', 'moy_cl': 18, 'n_compo': 18.5, 'coef': 2, 'appreciation': 'Tbien'},
    ]
    dummy_grades_p2 = [
        {'subject': 'E.C.M', 'moy_cl': 19.5, 'n_compo': 19, 'coef': 1, 'appreciation': 'Tbien'},
        {'subject': 'EPS', 'moy_cl': 15, 'n_compo': 16, 'coef': 1, 'appreciation': 'Bien'},
        {'subject': 'INFORMAT.', 'moy_cl': 20, 'n_compo': 19.5, 'coef': 1, 'appreciation': 'Tbien'},
        {'subject': 'DESSIN TECH.', 'moy_cl': 15, 'n_compo': 20, 'coef': 2, 'appreciation': 'Tbien'},
        {'subject': 'CONDUITE', 'moy_cl': 18, 'n_compo': 18, 'coef': 1, 'appreciation': 'Tbien'},
    ]
    dummy_summary_data = {
        'appr_p1': 'Tbien', 
        'appr_p2': 'Tbien', 
        'appr_globale':'Excellent', 
        'rank': '1er',
        'date_generated': '15/07/2024',
        'rank_1_moy': '18,50/20',
        'moy_p1_overall': '17,50 /20',
        'moy_p2_overall': '18,00 /20',
        'moy_annuelle': '17,75 /20'
    }

    generate_bulletin_pdf("bulletin_exemple_v2.pdf", dummy_student_data, dummy_grades_p1, dummy_grades_p2, dummy_summary_data)
    print("Bulletin d'exemple généré: bulletin_exemple_v2.pdf")
