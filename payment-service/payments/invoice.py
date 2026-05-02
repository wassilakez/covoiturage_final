# payments/invoice.py

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from django.conf import settings

def generate_pdf_receipt(transaction):
    """
    Génère un reçu PDF pour une transaction
    
    Args:
        transaction: Objet Transaction
    
    Returns:
        str: Chemin du fichier PDF généré
    """
    
    # Créer le nom du fichier
    filename = f"recu_{transaction.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(settings.RECEIPT_DIR, filename)
    
    # Créer le document PDF
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2E86AB'),
        spaceAfter=30,
        alignment=1  # Centré
    )
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        alignment=1
    )
    
    # Contenu du PDF
    story = []
    
    # En-tête avec logo et informations de la société
    story.append(Paragraph("PLATEFORME DE COVOITURAGE ALGÉRIE", title_style))
    story.append(Paragraph("Transport Inter-Villes - Solution Intelligente", company_style))
    story.append(Paragraph("www.covoiturage-algerie.dz | contact@covoiturage-algerie.dz", company_style))
    story.append(Spacer(1, 20))
    
    # Ligne de séparation
    story.append(Paragraph("=" * 80, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Titre du document
    receipt_title = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#27AE60'),
        alignment=1,
        spaceAfter=20
    )
    story.append(Paragraph("REÇU DE PAIEMENT OFFICIEL", receipt_title))
    story.append(Spacer(1, 10))
    
    # Informations de la transaction
    info_data = [
        ["N° Transaction:", str(transaction.id)],
        ["N° Réservation:", str(transaction.booking_id) if transaction.booking_id else "N/A"],
        ["Date:", transaction.completed_at.strftime('%d/%m/%Y à %H:%M') if transaction.completed_at else transaction.initiated_at.strftime('%d/%m/%Y à %H:%M')],
        ["Méthode de paiement:", transaction.get_payment_method_display() if transaction.payment_method else "En attente"],
        ["Statut:", transaction.get_status_display()],
    ]
    
    info_table = Table(info_data, colWidths=[5*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Détails du paiement
    story.append(Paragraph("DÉTAILS DU PAIEMENT", styles['Heading3']))
    story.append(Spacer(1, 10))
    
    payment_data = [
        ["Description", "Montant (DZD)"],
        ["Montant total du trajet", f"{transaction.amount:,.2f}"],
        ["Commission plateforme (10%)", f"{transaction.commission:,.2f}"],
        ["Montant reversé au chauffeur", f"{transaction.driver_amount:,.2f}"],
    ]
    
    payment_table = Table(payment_data, colWidths=[10*cm, 5*cm])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 20))
    
    # Détails du voyage (si disponibles)
    if transaction.metadata:
        story.append(Paragraph("DÉTAILS DU VOYAGE", styles['Heading3']))
        story.append(Spacer(1, 10))
        
        metadata = transaction.metadata
        trip_data = [
            ["Trajet:", f"{metadata.get('from_city', 'N/A')} → {metadata.get('to_city', 'N/A')}"],
            ["Date de départ:", metadata.get('departure_time', 'N/A')],
            ["Nombre de places:", str(metadata.get('seats_booked', 'N/A'))],
            ["Chauffeur:", metadata.get('driver_name', 'N/A')],
            ["Véhicule:", f"{metadata.get('vehicle_brand', '')} {metadata.get('vehicle_model', '')}"],
        ]
        
        trip_table = Table(trip_data, colWidths=[5*cm, 10*cm])
        trip_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        story.append(trip_table)
    
    story.append(Spacer(1, 30))
    
    # Pied de page
    footer_text = """
    <para align="center" fontSize="9" textColor="gray">
    ____________________________________________________<br/>
    Ce document fait foi de paiement pour la réservation effectuée.<br/>
    Merci d'avoir utilisé notre service de covoiturage en Algérie.<br/>
    Pour toute réclamation, contactez-nous dans les 48h suivant le trajet.
    </para>
    """
    story.append(Paragraph(footer_text, styles['Italic']))
    
    # Générer le PDF
    doc.build(story)
    
    return filepath