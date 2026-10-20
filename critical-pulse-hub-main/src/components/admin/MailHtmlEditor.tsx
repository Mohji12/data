import { useEffect, useMemo } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';

type Props = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  disabled?: boolean;
  minHeightClass?: string;
};

function isEmptyHtml(html: string): boolean {
  return !html || html.replace(/<[^>]*>/g, '').trim() === '';
}

export default function MailHtmlEditor({
  value,
  onChange,
  placeholder = 'Write the email body…',
  disabled = false,
  minHeightClass = 'min-h-[220px]',
}: Props) {
  const extensions = useMemo(
    () => [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Underline,
      Link.configure({ openOnClick: false, autolink: true }),
    ],
    [],
  );

  const editor = useEditor({
    extensions,
    content: value || '',
    editable: !disabled,
    editorProps: {
      attributes: {
        class: `prose prose-sm max-w-none focus:outline-none px-3 py-2 font-sans text-sm text-slate ${minHeightClass}`,
        'data-placeholder': placeholder,
      },
    },
    onUpdate: ({ editor: ed }) => {
      const html = ed.getHTML();
      onChange(isEmptyHtml(html) ? '' : html);
    },
  });

  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    const next = value || '';
    if (isEmptyHtml(current) && isEmptyHtml(next)) return;
    if (current !== next) {
      editor.commands.setContent(next || '', { emitUpdate: false });
    }
  }, [value, editor]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  if (!editor) return null;

  const btn = (active: boolean) =>
    `px-2.5 py-1.5 rounded-sm text-xs font-sans border transition-colors whitespace-nowrap ${
      active ? 'bg-slate text-chalk border-slate' : 'bg-chalk border-border-soft text-ink-secondary hover:bg-chalk-warm'
    } disabled:opacity-40`;

  const setLink = () => {
    const prev = String(editor.getAttributes('link').href || 'https://');
    const url = window.prompt('Link URL (https://…)', prev);
    if (url === null) return;
    if (!url.trim()) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url.trim() }).run();
  };

  return (
    <div className="w-full rounded-sm border border-border-soft bg-chalk overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b border-border-soft bg-chalk-warm/60">
        <button type="button" disabled={disabled} className={btn(editor.isActive('bold'))} onClick={() => editor.chain().focus().toggleBold().run()}>
          B
        </button>
        <button type="button" disabled={disabled} className={btn(editor.isActive('italic'))} onClick={() => editor.chain().focus().toggleItalic().run()}>
          I
        </button>
        <button type="button" disabled={disabled} className={btn(editor.isActive('underline'))} onClick={() => editor.chain().focus().toggleUnderline().run()}>
          U
        </button>
        <button type="button" disabled={disabled} className={btn(editor.isActive('heading', { level: 2 }))} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
          H2
        </button>
        <button type="button" disabled={disabled} className={btn(editor.isActive('bulletList'))} onClick={() => editor.chain().focus().toggleBulletList().run()}>
          List
        </button>
        <button type="button" disabled={disabled} className={btn(editor.isActive('link'))} onClick={setLink}>
          Link
        </button>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
