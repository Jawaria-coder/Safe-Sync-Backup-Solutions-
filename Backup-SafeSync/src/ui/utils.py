# src/ui/utils.py
import tkinter as tk

def create_status_badge(parent, status):
    """Creates a professional, color-coded status badge."""
    color_map = {
        "Success": ("#D1FAE5", "#059669"), 
        "Failed": ("#FEE2E2", "#EF4444"),  
        "Running": ("#DBEAFE", "#2563EB"), 
        "Healthy": ("#D1FAE5", "#059669"),  
        "Warning": ("#FEF3C7", "#F59E0B"), 
    }
    bg, fg = color_map.get(status, ("#E5E7EB", "#4B5563")) 

    label = tk.Label(parent, text=status, bg=bg, fg=fg, font=('Inter', 9, 'bold'), relief='flat', padx=7, pady=3)
    label.pack(side=tk.LEFT, padx=5, pady=5)

    return label
