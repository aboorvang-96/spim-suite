```python id="p4y7kd"
import webbrowser
import tkinter as tk
from tkinter import messagebox

APP_URL = "https://YOUR_HOSTED_URL"

try:
    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo(
        "SPIM Suite",
        "Opening SPIM Suite..."
    )

    webbrowser.open(APP_URL)

except Exception as e:
    messagebox.showerror(
        "SPIM Suite Error",
        str(e)
    )
```
