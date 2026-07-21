"""Bilingual Windows drag-and-drop desktop shell."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from maskingtool import config
from maskingtool.denylist.loader import add_deny_term, load_manual_terms
from maskingtool.gui_core import AmbiguousVaultError, HistoryStore, ProcessResult, commit_mask_preview, detect_file_action, diff_lines, prepare_mask_preview, process_dropped_file, remask_with_existing_vault

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


TEXT = {
    "en": {
        "subtitle": "Drop one file: plain documents are masked; documents containing tokens are restored.",
        "drop": "Drop a file here\nor click to choose a file", "drop_next": "Drop another file here\nor click to choose a file",
        "choose": "Choose file", "history": "History", "open": "Open output", "folder": "Open folder",
        "ready": "Ready", "working": "Processing…", "working_drop": "Processing, please wait…",
        "diff": "Diff preview (red = removed, green = added)", "mask_done": "Masking complete", "restore_done": "Restore complete",
        "no_entities": "No entities detected", "warning": "Warning", "output": "Output", "failed": "Processing failed",
        "one_title": "One file at a time", "one_body": "This version processes one file at a time.",
        "vault_title": "Choose a vault", "vault_body": "Multiple vaults resolve every token. Choose the correct record:",
        "use_vault": "Use selected vault", "history_title": "Processing history",
        "time": "Time", "action": "Action", "source": "Source", "history_output": "Output file",
        "use_current": "Use selected vault for current file", "select_title": "Choose a vault",
        "select_body": "Select a history item and choose a file to restore in the main window first.",
        "supported": "Supported documents", "all_files": "All files", "language": "Language",
        "mask": "Mask", "restore": "Restore",
        "mask_selected": "Mask selected text", "custom_terms": "Custom mask list",
        "select_text_title": "Select missed text", "select_text_body": "Select a missed name or company in the diff preview first.",
        "type_title": "Term type", "type_body": "How should this selected text be classified?",
        "person": "Person", "organization": "Organization", "added": "Added and re-masked",
        "added_body": "The term was saved to your custom list and all exact occurrences were masked in a new output file.",
        "terms_title": "Persistent custom mask list", "term": "Term", "type": "Type",
        "tutorial": "Tutorial", "preview_ready": "Preview ready — no file has been created",
        "preview_detail": "Review the changes below. Create the masked file only when you are satisfied.",
        "confirm_create": "Confirm and create masked file", "cancel_preview": "Cancel preview",
        "cancelled": "Preview cancelled — no file was created", "restore_detected": "Masked file detected",
        "restore_question": "This file contains masking tokens. Restore the original names now?",
        "restore_yes": "Restore names", "restore_no": "Cancel",
        "tutorial_title": "Quick tutorial", "tutorial_text": "1. Drop a document into the window.\n\n2. Review the red/green preview. No masked file exists yet.\n\n3. Select a missed name or company and click ‘Mask selected text’. It is saved for future files and the full document is re-scanned.\n\n4. Click ‘Confirm and create masked file’ only when the preview is correct.\n\n5. To restore, drop the .masked file back here. The app asks before restoring names.\n\nYour original file is never overwritten.",
        "tutorial_close": "Got it",
    },
    "zh": {
        "subtitle": "拖入一个文件：普通文件自动脱敏，含 token 的文件自动还原。",
        "drop": "将文件拖到这里\n或点击选择文件", "drop_next": "将另一个文件拖到这里\n或点击选择文件",
        "choose": "选择文件", "history": "查看历史", "open": "打开输出文件", "folder": "打开所在文件夹",
        "ready": "就绪", "working": "正在处理…", "working_drop": "正在处理，请稍候…",
        "diff": "差异预览（红色=删除，绿色=新增）", "mask_done": "脱敏完成", "restore_done": "还原完成",
        "no_entities": "未检测到实体", "warning": "警告", "output": "输出", "failed": "处理失败",
        "one_title": "一次一个文件", "one_body": "当前版本一次只处理一个文件。",
        "vault_title": "选择 Vault", "vault_body": "多个 Vault 都能解析全部 token，请选择正确记录：",
        "use_vault": "使用所选 Vault", "history_title": "处理历史",
        "time": "时间", "action": "动作", "source": "源文件", "history_output": "输出文件",
        "use_current": "用所选 Vault 处理当前文件", "select_title": "选择 Vault",
        "select_body": "请先选择历史项，并在主窗口选择一个待还原文件。",
        "supported": "支持的文档", "all_files": "所有文件", "language": "语言",
        "mask": "脱敏", "restore": "还原",
        "mask_selected": "遮蔽所选文字", "custom_terms": "自定义遮蔽列表",
        "select_text_title": "选择漏识别文字", "select_text_body": "请先在差异预览中划选漏掉的姓名或公司。",
        "type_title": "词语类型", "type_body": "所选文字应归类为什么类型？",
        "person": "人员", "organization": "公司/组织", "added": "已加入并重新脱敏",
        "added_body": "该词已保存到长期列表，全文所有完全相同的内容已在新输出文件中遮蔽。",
        "terms_title": "长期自定义遮蔽列表", "term": "词语", "type": "类型",
        "tutorial": "使用教程", "preview_ready": "预览已完成——尚未生成任何文件",
        "preview_detail": "请检查下方变化，确认无误后再生成脱敏文件。",
        "confirm_create": "确认并生成脱敏文件", "cancel_preview": "取消预览",
        "cancelled": "已取消预览——没有生成文件", "restore_detected": "检测到脱敏文件",
        "restore_question": "该文件包含脱敏 token。现在要还原原始姓名吗？",
        "restore_yes": "还原姓名", "restore_no": "取消",
        "tutorial_title": "快速使用教程", "tutorial_text": "1. 将文档拖入窗口。\n\n2. 检查红绿预览，此时尚未生成脱敏文件。\n\n3. 如果有漏识别的姓名或公司，在预览中划选后点击“遮蔽所选文字”。该词会保存供未来文件使用，并重新扫描全文。\n\n4. 只有预览确认无误后，点击“确认并生成脱敏文件”。\n\n5. 需要还原时，把 .masked 文件拖回窗口；软件会先明确询问是否还原姓名。\n\n软件永远不会覆盖原文件。",
        "tutorial_close": "知道了",
    },
}

TEXT["en"].update({
    "tour_back": "Back", "tour_next": "Next", "tour_skip": "Skip", "tour_finish": "Finish",
    "tour_language_title": "Choose your language", "tour_language_body": "Use this selector at any time. English is the default and your choice is remembered.",
    "tour_drop_title": "1. Add a document", "tour_drop_body": "Drop one file here, or click the area to browse. Supported: text, Markdown, DOCX and PDF.",
    "tour_diff_title": "2. Review the preview", "tour_diff_body": "Red is original text; green is the masked result. Example: Alice at Acme becomes ⟦PERSON_001⟧ at ⟦ORG_001⟧. No file exists yet.",
    "tour_select_title": "3. Correct anything missed", "tour_select_body": "Select a missed name or company in the preview, then click this button. Every exact occurrence is re-masked and saved for future documents.",
    "tour_confirm_title": "4. Create only when ready", "tour_confirm_body": "This is the only button that writes the masked file, Vault and history. Review first, then confirm.",
    "tour_terms_title": "Your permanent mask list", "tour_terms_body": "Open this list to see names and companies you manually added for future documents.",
    "tour_history_title": "Find earlier results", "tour_history_body": "History connects each masked output to its Vault so it can be restored safely later.",
    "tour_restore_title": "5. Restore a masked file", "tour_restore_body": "Drop the .masked file back into the same area. A clear confirmation asks whether to restore names; restored output never overwrites the masked file.",
})
TEXT["zh"].update({
    "tour_back": "上一步", "tour_next": "下一步", "tour_skip": "跳过", "tour_finish": "完成",
    "tour_language_title": "选择界面语言", "tour_language_body": "可随时在这里切换。默认使用英文，软件会记住你的选择。",
    "tour_drop_title": "1. 添加文档", "tour_drop_body": "把一个文件拖到这里，也可以点击此区域选择文件。支持文本、Markdown、DOCX 和 PDF。",
    "tour_diff_title": "2. 检查预览", "tour_diff_body": "红色是原文，绿色是脱敏结果。例如 Alice at Acme 会变成 ⟦PERSON_001⟧ at ⟦ORG_001⟧。此时尚未生成文件。",
    "tour_select_title": "3. 补充漏识别内容", "tour_select_body": "在预览中划选漏掉的姓名或公司，再点击这个按钮。全文相同内容会重新脱敏，并保存供未来文档使用。",
    "tour_confirm_title": "4. 确认后才生成", "tour_confirm_body": "只有点击此按钮才会写入脱敏文件、Vault 和历史。请先检查，确认无误后再生成。",
    "tour_terms_title": "长期遮蔽列表", "tour_terms_body": "这里可以查看你人工添加、以后处理其他文件时也会自动遮蔽的姓名和公司。",
    "tour_history_title": "查找之前的结果", "tour_history_body": "历史记录把每个脱敏输出与 Vault 对应起来，方便以后安全还原。",
    "tour_restore_title": "5. 还原脱敏文件", "tour_restore_body": "把 .masked 文件重新拖回同一区域。软件会明确询问是否还原姓名，还原结果不会覆盖脱敏文件。",
})


def translated(language: str, key: str) -> str:
    return TEXT.get(language, TEXT["en"]).get(key, TEXT["en"][key])


TOUR_STEP_KEYS = ("language", "drop", "diff", "select", "confirm", "terms", "history", "restore")


class CoachTour:
    """Mobile-style coach marks anchored to real widgets."""
    COLOR = "#1677ff"

    def __init__(self, root, steps, tr, on_close):
        self.root, self.steps, self.tr, self.on_close = root, steps, tr, on_close
        self.index, self.borders, self.card = 0, [], None
        self.show()

    def _destroy_windows(self):
        for window in self.borders:
            try: window.destroy()
            except tk.TclError: pass
        self.borders = []
        if self.card:
            try: self.card.destroy()
            except tk.TclError: pass
            self.card = None

    def _border(self, x, y, width, height):
        window = tk.Toplevel(self.root); window.overrideredirect(True)
        window.configure(bg=self.COLOR); window.attributes("-topmost", True)
        window.geometry(f"{max(1, width)}x{max(1, height)}+{x}+{y}")
        self.borders.append(window)

    def show(self):
        self._destroy_windows(); self.root.update_idletasks()
        target, title_key, body_key = self.steps[self.index]
        target.update_idletasks()
        x, y = target.winfo_rootx(), target.winfo_rooty()
        width, height, pad, line = target.winfo_width(), target.winfo_height(), 6, 4
        self._border(x-pad, y-pad, width+pad*2, line)
        self._border(x-pad, y+height+pad-line, width+pad*2, line)
        self._border(x-pad, y-pad, line, height+pad*2)
        self._border(x+width+pad-line, y-pad, line, height+pad*2)

        card = tk.Toplevel(self.root); self.card = card
        card.overrideredirect(True); card.attributes("-topmost", True)
        frame = tk.Frame(card, bg="white", highlightbackground=self.COLOR, highlightthickness=2, padx=16, pady=14)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=self.tr(title_key), bg="white", fg="#172b4d", font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x")
        tk.Label(frame, text=self.tr(body_key), bg="white", fg="#354052", font=("Segoe UI", 10), wraplength=370, justify="left", anchor="w").pack(fill="x", pady=(8, 12))
        controls = tk.Frame(frame, bg="white"); controls.pack(fill="x")
        tk.Label(controls, text=f"{self.index+1} / {len(self.steps)}", bg="white", fg="#6b778c").pack(side="left")
        ttk.Button(controls, text=self.tr("tour_skip"), command=self.close).pack(side="left", padx=8)
        if self.index:
            ttk.Button(controls, text=self.tr("tour_back"), command=self.back).pack(side="right", padx=4)
        final = self.index == len(self.steps)-1
        ttk.Button(controls, text=self.tr("tour_finish" if final else "tour_next"), command=self.close if final else self.next).pack(side="right")
        card.update_idletasks(); cw, ch = max(420, card.winfo_reqwidth()), card.winfo_reqheight()
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        cx = min(max(10, x), screen_w-cw-10)
        cy = y+height+14 if y+height+14+ch < screen_h else max(10, y-ch-14)
        card.geometry(f"{cw}x{ch}+{cx}+{cy}")

    def next(self): self.index += 1; self.show()
    def back(self): self.index -= 1; self.show()
    def close(self): self._destroy_windows(); self.on_close()


class MaskingToolApp:
    def __init__(self, root: tk.Tk):
        self.root, self.history = root, HistoryStore()
        self.output_path = self.current_path = None
        self.current_result = None
        self.current_preview = None
        self.review_id = None
        self.session_terms = []
        self.busy = False
        saved = config.load_settings().get("gui_language", "en")
        self.language = saved if saved in TEXT else "en"
        root.geometry("920x680"); root.minsize(720, 520)
        self._build(); self._apply_language()
        if not config.load_settings().get("gui_tutorial_seen", False):
            self.root.after(250, self.show_tutorial)

    def tr(self, key): return translated(self.language, key)

    def _build(self):
        shell = ttk.Frame(self.root, padding=16); shell.pack(fill="both", expand=True)
        top = ttk.Frame(shell); top.pack(fill="x")
        ttk.Label(top, text="Content Masking Tool", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.language_var = tk.StringVar(value="English" if self.language == "en" else "中文")
        self.language_box = ttk.Combobox(top, textvariable=self.language_var, values=("English", "中文"), state="readonly", width=10)
        self.language_box.pack(side="right"); self.language_box.bind("<<ComboboxSelected>>", self._change_language)
        self.language_label = ttk.Label(top); self.language_label.pack(side="right", padx=6)
        self.subtitle = ttk.Label(shell); self.subtitle.pack(anchor="w", pady=(2, 12))
        self.drop = tk.Label(shell, relief="ridge", bd=2, bg="#f4f6f8", fg="#354052", height=7, font=("Segoe UI", 13), cursor="hand2")
        self.drop.pack(fill="x"); self.drop.bind("<Button-1>", lambda _e: self.choose_file())
        if DND_FILES:
            self.drop.drop_target_register(DND_FILES); self.drop.dnd_bind("<<Drop>>", self._on_drop)
        bar = ttk.Frame(shell); bar.pack(fill="x", pady=10)
        self.choose_button = ttk.Button(bar, command=self.choose_file); self.choose_button.pack(side="left")
        self.history_button = ttk.Button(bar, command=self.show_history); self.history_button.pack(side="left", padx=8)
        self.tutorial_button = ttk.Button(bar, command=self.show_tutorial); self.tutorial_button.pack(side="left")
        self.open_button = ttk.Button(bar, command=self.open_output, state="disabled"); self.open_button.pack(side="right")
        self.folder_button = ttk.Button(bar, command=self.open_folder, state="disabled"); self.folder_button.pack(side="right", padx=8)
        self.status = tk.StringVar(); self.details = tk.StringVar()
        ttk.Label(shell, textvariable=self.status, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(shell, textvariable=self.details, wraplength=860).pack(anchor="w", pady=(2, 8))
        review = ttk.Frame(shell); review.pack(fill="x")
        self.diff_label = ttk.Label(review); self.diff_label.pack(side="left")
        self.terms_button = ttk.Button(review, command=self.show_custom_terms); self.terms_button.pack(side="right")
        self.mask_selected_button = ttk.Button(review, command=self.mask_selected, state="disabled"); self.mask_selected_button.pack(side="right", padx=8)
        self.cancel_button = ttk.Button(review, command=self.cancel_preview, state="disabled"); self.cancel_button.pack(side="right")
        self.confirm_button = ttk.Button(review, command=self.confirm_preview, state="disabled"); self.confirm_button.pack(side="right", padx=8)
        frame = ttk.Frame(shell); frame.pack(fill="both", expand=True, pady=(4, 0))
        self.diff = tk.Text(frame, wrap="none", state="disabled", exportselection=False, font=("Consolas", 10))
        ys, xs = ttk.Scrollbar(frame, orient="vertical", command=self.diff.yview), ttk.Scrollbar(frame, orient="horizontal", command=self.diff.xview)
        self.diff.configure(yscrollcommand=ys.set, xscrollcommand=xs.set); self.diff.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns"); xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        self.diff.tag_configure("delete", foreground="#a12622", background="#ffeef0")
        self.diff.tag_configure("insert", foreground="#116329", background="#dafbe1"); self.diff.tag_configure("equal", foreground="#57606a")

    def _apply_language(self):
        self.root.title("Content Masking Tool"); self.language_label.configure(text=self.tr("language") + ":")
        self.subtitle.configure(text=self.tr("subtitle")); self.drop.configure(text=self.tr("drop"))
        self.choose_button.configure(text=self.tr("choose")); self.history_button.configure(text=self.tr("history"))
        self.open_button.configure(text=self.tr("open")); self.folder_button.configure(text=self.tr("folder"))
        self.diff_label.configure(text=self.tr("diff")); self.status.set(self.tr("ready"))
        self.mask_selected_button.configure(text=self.tr("mask_selected")); self.terms_button.configure(text=self.tr("custom_terms"))
        self.tutorial_button.configure(text=self.tr("tutorial")); self.confirm_button.configure(text=self.tr("confirm_create")); self.cancel_button.configure(text=self.tr("cancel_preview"))

    def _change_language(self, _event=None):
        self.language = "zh" if self.language_var.get() == "中文" else "en"
        config.save_settings({"gui_language": self.language}); self._apply_language()

    def choose_file(self):
        path = filedialog.askopenfilename(filetypes=[(self.tr("supported"), "*.md *.markdown *.txt *.html *.htm *.docx *.pdf"), (self.tr("all_files"), "*.*")])
        if path: self.process(Path(path))

    def _on_drop(self, event):
        paths = list(self.root.tk.splitlist(event.data))
        if len(paths) != 1:
            messagebox.showwarning(self.tr("one_title"), self.tr("one_body")); return
        self.process(Path(paths[0]))

    def process(self, path: Path, selected_vault_id=None, restore_confirmed=False):
        if self.busy: return
        self.busy, self.current_path = True, path
        self.status.set(self.tr("working")); self.details.set(str(path)); self.drop.configure(text=self.tr("working_drop"))
        def work():
            try:
                action = "restore" if selected_vault_id else detect_file_action(path, self.history)
                if action == "mask":
                    preview = prepare_mask_preview(path)
                    self.root.after(0, lambda: self._preview_ready(preview))
                elif not restore_confirmed:
                    self.root.after(0, lambda: self._confirm_restore(path, selected_vault_id))
                else:
                    result = process_dropped_file(path, history=self.history, selected_vault_id=selected_vault_id)
                    self.root.after(0, lambda: self._success(result))
            except AmbiguousVaultError as exc:
                self.root.after(0, lambda error=exc: self._choose_vault(path, error))
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._failure(error))
        threading.Thread(target=work, daemon=True).start()

    def _preview_ready(self, preview):
        self.busy, self.current_preview, self.current_result = False, preview, None
        self.current_path = preview.input_path; self.status.set(self.tr("preview_ready"))
        self.details.set(f"{self.tr('preview_detail')}\n{self.tr('output')}: {preview.proposed_output_path}")
        self.drop.configure(text=self.tr("drop_next")); self._show_diff(preview.before_text, preview.masked_text)
        self.confirm_button.configure(state="normal"); self.cancel_button.configure(state="normal"); self.mask_selected_button.configure(state="normal")

    def confirm_preview(self):
        if not self.current_preview or self.busy: return
        preview = self.current_preview; self.busy = True; self.status.set(self.tr("working"))
        self.confirm_button.configure(state="disabled"); self.cancel_button.configure(state="disabled"); self.mask_selected_button.configure(state="disabled")
        def work():
            try:
                result = commit_mask_preview(preview, history=self.history)
                self.root.after(0, lambda: self._success(result))
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._failure(error))
        threading.Thread(target=work, daemon=True).start()

    def _cancel_pending_review(self):
        if not self.review_id:
            return
        from maskingtool import review as _review
        try:
            _review.cancel_review(self.review_id)
        except Exception:
            pass
        self.review_id = None

    def cancel_preview(self):
        if self.busy: return
        self._cancel_pending_review()
        self.current_preview = None; self.status.set(self.tr("cancelled")); self.details.set("")
        self.confirm_button.configure(state="disabled"); self.cancel_button.configure(state="disabled"); self.mask_selected_button.configure(state="disabled")
        self.diff.configure(state="normal"); self.diff.delete("1.0", "end"); self.diff.configure(state="disabled")

    def _confirm_restore(self, path, selected_vault_id=None):
        self.busy = False; self.status.set(self.tr("restore_detected")); self.details.set(str(path)); self.drop.configure(text=self.tr("drop"))
        win = tk.Toplevel(self.root); win.title(self.tr("restore_detected")); win.geometry("520x190"); win.transient(self.root); win.grab_set()
        ttk.Label(win, text=self.tr("restore_detected"), font=("Segoe UI", 16, "bold"), padding=(18, 18, 18, 4)).pack(anchor="w")
        ttk.Label(win, text=self.tr("restore_question"), wraplength=480, padding=18).pack(anchor="w")
        buttons = ttk.Frame(win); buttons.pack(pady=(0, 16))
        def restore():
            win.destroy(); self.process(path, selected_vault_id, restore_confirmed=True)
        ttk.Button(buttons, text=self.tr("restore_yes"), command=restore).pack(side="left", padx=8)
        ttk.Button(buttons, text=self.tr("restore_no"), command=win.destroy).pack(side="left", padx=8)

    def _success(self, result: ProcessResult):
        self.busy, self.output_path, self.current_result, self.current_preview = False, result.output_path, result, None
        if self.review_id and result.action == "mask":
            from maskingtool import review as _review
            try:
                _review.complete_review(self.review_id, {
                    "masked_file_path": str(result.output_path),
                    "vault_id": result.vault_id,
                    "output_format": result.output_format if hasattr(result, "output_format") else "markdown",
                    "entity_counts": result.entity_counts,
                    "manual_terms_added": list(self.session_terms),
                    "warnings": result.warnings,
                })
                self.review_id = None  # decided; window close must not cancel
            except Exception:
                pass
        self.status.set(self.tr("mask_done" if result.action == "mask" else "restore_done"))
        counts = ", ".join(f"{k}: {v}" for k, v in result.entity_counts.items()) or self.tr("no_entities")
        warning = (f"; {self.tr('warning')}: " + " | ".join(result.warnings)) if result.warnings else ""
        self.details.set(f"{self.tr('output')}: {result.output_path}\nVault ID: {result.vault_id}; {counts}{warning}")
        self.drop.configure(text=self.tr("drop_next")); self.open_button.configure(state="normal"); self.folder_button.configure(state="normal")
        self.mask_selected_button.configure(state="normal" if result.action == "mask" else "disabled")
        self.confirm_button.configure(state="disabled"); self.cancel_button.configure(state="disabled")
        self._show_diff(result.before_text, result.after_text)

    def _failure(self, exc):
        self.busy = False; self.status.set(self.tr("failed")); self.details.set(f"{type(exc).__name__}: {exc}")
        self.drop.configure(text=self.tr("drop")); messagebox.showerror(self.tr("failed"), str(exc))

    def _choose_vault(self, path, exc):
        self.busy = False; win = tk.Toplevel(self.root); win.title(self.tr("vault_title")); win.geometry("680x320")
        ttk.Label(win, text=self.tr("vault_body"), padding=10).pack(anchor="w")
        box = tk.Listbox(win, font=("Consolas", 10)); box.pack(fill="both", expand=True, padx=10)
        for vault in exc.candidates: box.insert("end", f"{vault.created_at}  {vault.source_filename}  {vault.vault_id}")
        box.selection_set(0)
        def use():
            selected = box.curselection()
            if selected: win.destroy(); self.process(path, exc.candidates[selected[0]].vault_id, restore_confirmed=True)
        ttk.Button(win, text=self.tr("use_vault"), command=use).pack(pady=10)

    def _show_diff(self, before, after):
        self.diff.configure(state="normal"); self.diff.delete("1.0", "end")
        for kind, line in diff_lines(before, after): self.diff.insert("end", {"delete": "- ", "insert": "+ ", "equal": "  "}[kind] + line, kind)
        self.diff.configure(state="disabled")

    def show_history(self):
        win = tk.Toplevel(self.root); win.title(self.tr("history_title")); win.geometry("900x420")
        cols = ("time", "action", "source", "output", "vault"); tree = ttk.Treeview(win, columns=cols, show="headings")
        for col, title, width in zip(cols, (self.tr("time"), self.tr("action"), self.tr("source"), self.tr("history_output"), "Vault ID"), (170, 70, 160, 300, 180)):
            tree.heading(col, text=title); tree.column(col, width=width)
        records = self.history.records()
        for i, row in enumerate(records): tree.insert("", "end", iid=str(i), values=(row.created_at[:19], self.tr(row.action), row.source_filename, row.output_path, row.vault_id))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        def use_vault():
            selected = tree.selection()
            if not selected or not self.current_path:
                messagebox.showinfo(self.tr("select_title"), self.tr("select_body")); return
            win.destroy(); self.process(self.current_path, records[int(selected[0])].vault_id)
        ttk.Button(win, text=self.tr("use_current"), command=use_vault).pack(pady=(0, 10))

    def mask_selected(self):
        if not self.current_preview and (not self.current_result or self.current_result.action != "mask"): return
        try:
            term = self.diff.get("sel.first", "sel.last").strip()
        except tk.TclError:
            term = ""
        if not term or "\n" in term or "\r" in term:
            messagebox.showinfo(self.tr("select_text_title"), self.tr("select_text_body")); return
        win = tk.Toplevel(self.root); win.title(self.tr("type_title")); win.geometry("420x150"); win.transient(self.root); win.grab_set()
        ttk.Label(win, text=f"{self.tr('type_body')}\n\n“{term}”", padding=12).pack()
        buttons = ttk.Frame(win); buttons.pack()
        def choose(entity_type):
            win.destroy(); self.session_terms.append(term); self._apply_manual_term(term, entity_type)
        ttk.Button(buttons, text=self.tr("person"), command=lambda: choose("PERSON")).pack(side="left", padx=8)
        ttk.Button(buttons, text=self.tr("organization"), command=lambda: choose("ORG")).pack(side="left", padx=8)

    def _apply_manual_term(self, term, entity_type):
        if self.busy: return
        result, preview = self.current_result, self.current_preview; self.busy = True
        self.status.set(self.tr("working")); self.mask_selected_button.configure(state="disabled")
        def work():
            try:
                add_deny_term(term, entity_type)
                if preview:
                    corrected = prepare_mask_preview(preview.input_path)
                    self.root.after(0, lambda: self._preview_ready(corrected))
                else:
                    corrected = remask_with_existing_vault(result.input_path, result.vault_id, history=self.history)
                    self.root.after(0, lambda: self._manual_success(corrected))
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._failure(error))
        threading.Thread(target=work, daemon=True).start()

    def _manual_success(self, result):
        self._success(result)
        messagebox.showinfo(self.tr("added"), self.tr("added_body"))

    def show_custom_terms(self):
        win = tk.Toplevel(self.root); win.title(self.tr("terms_title")); win.geometry("620x420")
        tree = ttk.Treeview(win, columns=("type", "term"), show="headings")
        tree.heading("type", text=self.tr("type")); tree.heading("term", text=self.tr("term"))
        tree.column("type", width=140); tree.column("term", width=430)
        for item in load_manual_terms():
            label = self.tr("person" if item["entity_type"] == "PERSON" else "organization")
            tree.insert("", "end", values=(label, item["term"]))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def show_tutorial(self):
        existing = getattr(self, "active_tour", None)
        if existing:
            existing._destroy_windows()
        steps = [
            (self.language_box, "tour_language_title", "tour_language_body"),
            (self.drop, "tour_drop_title", "tour_drop_body"),
            (self.diff, "tour_diff_title", "tour_diff_body"),
            (self.mask_selected_button, "tour_select_title", "tour_select_body"),
            (self.confirm_button, "tour_confirm_title", "tour_confirm_body"),
            (self.terms_button, "tour_terms_title", "tour_terms_body"),
            (self.history_button, "tour_history_title", "tour_history_body"),
            (self.drop, "tour_restore_title", "tour_restore_body"),
        ]
        def close():
            config.save_settings({"gui_tutorial_seen": True}); self.active_tour = None
        self.active_tour = CoachTour(self.root, steps, self.tr, close)

    def open_output(self):
        if self.output_path: open_local_path(self.output_path)
    def open_folder(self):
        if self.output_path: open_local_path(self.output_path.parent)


def open_local_path(path: Path):
    """Open a file/folder with the platform's native desktop application."""
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _attach_review(app, root, review_id: str, file_path: str):
    """Wire a mandatory-review job into the GUI: register our PID, auto-load
    the file, and mark the review cancelled if the window closes undecided."""
    import os as _os

    from maskingtool import review as _review

    app.review_id = review_id
    try:
        _review.set_gui_pid(review_id, _os.getpid())
    except Exception:
        pass

    def on_close():
        app._cancel_pending_review()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(200, lambda: app.process(Path(file_path)))


def _hide_console_on_windows():
    if os.name == "nt":
        try:
            import ctypes; ctypes.windll.kernel32.FreeConsole()
        except OSError: pass


def main(review_id: str | None = None, file: str | None = None):
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk(); _hide_console_on_windows()
    app = MaskingToolApp(root)
    if review_id and file:
        _attach_review(app, root, review_id, file)
    root.mainloop()
    return 0
