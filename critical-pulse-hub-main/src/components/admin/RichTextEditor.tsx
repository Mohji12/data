import { useEffect, useMemo, useState } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { TextStyle } from '@tiptap/extension-text-style';
import Color from '@tiptap/extension-color';
import Highlight from '@tiptap/extension-highlight';
import { Extension } from '@tiptap/core';

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    fontSize: {
      setFontSize: (size: string) => ReturnType;
      unsetFontSize: () => ReturnType;
    };
    backgroundColor: {
      setBackgroundColor: (color: string) => ReturnType;
      unsetBackgroundColor: () => ReturnType;
    };
  }
}

const FontSize = Extension.create({
  name: 'fontSize',
  addOptions() {
    return { types: ['textStyle'] };
  },
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (element: HTMLElement) => element.style.fontSize || null,
            renderHTML: (attributes: { fontSize?: string | null }) => {
              if (!attributes.fontSize) return {};
              return { style: `font-size: ${attributes.fontSize}` };
            },
          },
        },
      },
    ];
  },
  addCommands() {
    return {
      setFontSize:
        (fontSize: string) =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize }).run(),
      unsetFontSize:
        () =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize: null }).removeEmptyTextStyle().run(),
    };
  },
});

const BackgroundColor = Extension.create({
  name: 'backgroundColor',
  addOptions() {
    return { types: ['textStyle'] };
  },
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          backgroundColor: {
            default: null,
            parseHTML: (element: HTMLElement) => element.style.backgroundColor || null,
            renderHTML: (attributes: { backgroundColor?: string | null }) => {
              if (!attributes.backgroundColor) return {};
              return { style: `background-color: ${attributes.backgroundColor}` };
            },
          },
        },
      },
    ];
  },
  addCommands() {
    return {
      setBackgroundColor:
        (backgroundColor: string) =>
        ({ chain }) =>
          chain().setMark('textStyle', { backgroundColor }).run(),
      unsetBackgroundColor:
        () =>
        ({ chain }) =>
          chain().setMark('textStyle', { backgroundColor: null }).removeEmptyTextStyle().run(),
    };
  },
});

const FONT_SIZES = ['12px', '14px', '16px', '18px', '20px', '24px', '28px'];
const TEXT_COLORS = [
  '#0f2744',
  '#1e3a5f',
  '#0d9488',
  '#dc2626',
  '#ca8a04',
  '#7c3aed',
  '#111827',
  '#6b7280',
  '#ffffff',
];
const BG_COLORS = [
  '#fef08a',
  '#fde68a',
  '#fecaca',
  '#bbf7d0',
  '#bfdbfe',
  '#e9d5ff',
  '#fce7f3',
  '#e5e7eb',
];
const HIGHLIGHT_COLORS = ['#fef08a', '#fde047', '#fdba74', '#86efac', '#7dd3fc', '#f9a8d4', '#c4b5fd'];
const SYMBOLS = [
  '₹',
  '$',
  '€',
  '£',
  '©',
  '®',
  '™',
  '•',
  '–',
  '—',
  '…',
  '★',
  '☆',
  '✓',
  '✔',
  '✗',
  '→',
  '←',
  '↑',
  '↓',
  '°',
  '±',
  '½',
  '¼',
  '§',
  '¶',
  '⚠',
  'ℹ',
];

function isEmptyHtml(html: string): boolean {
  const stripped = html
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, '')
    .trim();
  return !stripped;
}

function currentHeadingLevel(editor: {
  isActive: (name: string, attrs?: { level: number }) => boolean;
}): string {
  for (const level of [2, 3, 4] as const) {
    if (editor.isActive('heading', { level })) return String(level);
  }
  return '';
}

type Props = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  minHeightClass?: string;
};

type Popover = 'text' | 'bg' | 'highlight' | 'symbols' | null;

export default function RichTextEditor({
  value,
  onChange,
  placeholder = 'Write description…',
  disabled = false,
  className = '',
  minHeightClass = 'min-h-[320px]',
}: Props) {
  const [open, setOpen] = useState<Popover>(null);

  const extensions = useMemo(
    () => [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
      }),
      Underline,
      TextStyle,
      Color,
      BackgroundColor,
      FontSize,
      Highlight.configure({ multicolor: true }),
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
      active
        ? 'bg-slate text-chalk border-slate'
        : 'bg-chalk border-border-soft text-ink-secondary hover:bg-chalk-warm'
    } disabled:opacity-40`;

  const togglePop = (key: Popover) => setOpen((cur) => (cur === key ? null : key));

  const colorSwatches = (
    colors: string[],
    onPick: (c: string) => void,
    onReset: () => void,
    resetLabel: string,
  ) => (
    <div className="absolute z-30 top-full left-0 mt-1 p-2 rounded-sm border border-border-soft bg-chalk shadow-md flex flex-wrap gap-1.5 w-[156px]">
      {colors.map((c) => (
        <button
          key={c}
          type="button"
          className="w-6 h-6 rounded-sm border border-border-soft"
          style={{ backgroundColor: c }}
          title={c}
          onClick={() => {
            onPick(c);
            setOpen(null);
          }}
        />
      ))}
      <button
        type="button"
        className="w-full mt-1 text-[10px] font-mono text-ink-faint hover:text-slate"
        onClick={() => {
          onReset();
          setOpen(null);
        }}
      >
        {resetLabel}
      </button>
    </div>
  );

  return (
    <div className={`w-full rounded-sm border border-border-soft bg-chalk overflow-visible ${className}`}>
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 border-b border-border-soft bg-chalk-warm/60 w-full">
        {/* Text style */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={disabled}
            className={btn(editor.isActive('bold'))}
            onClick={() => editor.chain().focus().toggleBold().run()}
            title="Bold"
          >
            <strong>B</strong>
          </button>
          <button
            type="button"
            disabled={disabled}
            className={btn(editor.isActive('italic'))}
            onClick={() => editor.chain().focus().toggleItalic().run()}
            title="Italic"
          >
            <em>I</em>
          </button>
          <button
            type="button"
            disabled={disabled}
            className={btn(editor.isActive('underline'))}
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            title="Underline"
          >
            <span className="underline">U</span>
          </button>
          <button
            type="button"
            disabled={disabled}
            className={btn(
              editor.isActive('highlight') ||
                Boolean(editor.getAttributes('textStyle').backgroundColor),
            )}
            onClick={() => {
              editor.chain().focus().toggleHighlight({ color: '#fef08a' }).run();
              setOpen(null);
            }}
            title="Highlight selection"
          >
            Highlight
          </button>
          <button
            type="button"
            disabled={disabled}
            className={btn(
              editor.isActive('bold') &&
                editor.isActive('highlight', { color: '#fde047' }),
            )}
            onClick={() => {
              editor
                .chain()
                .focus()
                .setBold()
                .setHighlight({ color: '#fde047' })
                .setColor('#b45309')
                .run();
              setOpen(null);
            }}
            title="Emphasize important batch info"
          >
            Important
          </button>
        </div>

        <span className="hidden sm:inline-block w-px h-5 bg-border-soft mx-0.5" />

        {/* Structure */}
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 text-[10px] font-mono text-ink-faint uppercase">
            Heading
            <select
              disabled={disabled}
              className="bg-chalk border border-border-soft rounded-sm py-1.5 px-2 text-xs text-ink normal-case min-w-[6rem]"
              value={currentHeadingLevel(editor)}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) editor.chain().focus().setParagraph().run();
                else editor.chain().focus().toggleHeading({ level: Number(v) as 2 | 3 | 4 }).run();
              }}
            >
              <option value="">Paragraph</option>
              <option value="2">Heading 2</option>
              <option value="3">Heading 3</option>
              <option value="4">Heading 4</option>
            </select>
          </label>
          <button
            type="button"
            disabled={disabled}
            className={btn(editor.isActive('bulletList'))}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            title="Bullet list"
          >
            • List
          </button>
          <button
            type="button"
            disabled={disabled}
            className={btn(editor.isActive('orderedList'))}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            title="Numbered list"
          >
            1. List
          </button>
        </div>

        <span className="hidden md:inline-block w-px h-5 bg-border-soft mx-0.5" />

        {/* Size / colours */}
        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 text-[10px] font-mono text-ink-faint uppercase">
            Size
            <select
              disabled={disabled}
              className="bg-chalk border border-border-soft rounded-sm py-1.5 px-2 text-xs text-ink normal-case min-w-[5.5rem]"
              value={editor.getAttributes('textStyle').fontSize || ''}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) editor.chain().focus().unsetFontSize().run();
                else editor.chain().focus().setFontSize(v).run();
              }}
            >
              <option value="">Default</option>
              {FONT_SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>

          <div className="relative">
            <button
              type="button"
              disabled={disabled}
              className={btn(open === 'text' || Boolean(editor.getAttributes('textStyle').color))}
              onClick={() => togglePop('text')}
              title="Text colour"
            >
              Text colour
            </button>
            {open === 'text' &&
              colorSwatches(
                TEXT_COLORS,
                (c) => editor.chain().focus().setColor(c).run(),
                () => editor.chain().focus().unsetColor().run(),
                'Reset text colour',
              )}
          </div>

          <div className="relative">
            <button
              type="button"
              disabled={disabled}
              className={btn(
                open === 'bg' || Boolean(editor.getAttributes('textStyle').backgroundColor),
              )}
              onClick={() => togglePop('bg')}
              title="Background colour"
            >
              Background
            </button>
            {open === 'bg' &&
              colorSwatches(
                BG_COLORS,
                (c) => editor.chain().focus().setBackgroundColor(c).run(),
                () => editor.chain().focus().unsetBackgroundColor().run(),
                'Reset background',
              )}
          </div>

          <div className="relative">
            <button
              type="button"
              disabled={disabled}
              className={btn(open === 'highlight' || editor.isActive('highlight'))}
              onClick={() => togglePop('highlight')}
              title="Highlight colour"
            >
              Highlight colour
            </button>
            {open === 'highlight' &&
              colorSwatches(
                HIGHLIGHT_COLORS,
                (c) => editor.chain().focus().toggleHighlight({ color: c }).run(),
                () => editor.chain().focus().unsetHighlight().run(),
                'Remove highlight',
              )}
          </div>

          <div className="relative">
            <button
              type="button"
              disabled={disabled}
              className={btn(open === 'symbols')}
              onClick={() => togglePop('symbols')}
              title="Insert symbol"
            >
              Symbol
            </button>
            {open === 'symbols' && (
              <div className="absolute z-30 top-full left-0 mt-1 p-2 rounded-sm border border-border-soft bg-chalk shadow-md grid grid-cols-6 gap-1 w-[200px]">
                {SYMBOLS.map((sym) => (
                  <button
                    key={sym}
                    type="button"
                    className="h-8 rounded-sm border border-border-soft hover:bg-chalk-warm text-sm"
                    onClick={() => {
                      editor.chain().focus().insertContent(sym).run();
                      setOpen(null);
                    }}
                  >
                    {sym}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <span className="hidden md:inline-block w-px h-5 bg-border-soft mx-0.5" />

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={disabled || !editor.can().undo()}
            className={btn(false)}
            onClick={() => editor.chain().focus().undo().run()}
            title="Undo"
          >
            Undo
          </button>
          <button
            type="button"
            disabled={disabled || !editor.can().redo()}
            className={btn(false)}
            onClick={() => editor.chain().focus().redo().run()}
            title="Redo"
          >
            Redo
          </button>
          <button
            type="button"
            disabled={disabled}
            className={btn(false)}
            onClick={() => editor.chain().focus().clearNodes().unsetAllMarks().run()}
            title="Clear formatting"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="w-full bg-chalk">
        <EditorContent editor={editor} />
      </div>
      <style>{`
        .ProseMirror {
          min-height: inherit;
          width: 100%;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          color: #9ca3af;
          content: attr(data-placeholder);
          float: left;
          height: 0;
          pointer-events: none;
        }
        .ProseMirror p { margin: 0.4em 0; }
        .ProseMirror ul, .ProseMirror ol { padding-left: 1.25rem; margin: 0.4em 0; }
        .ProseMirror h2 { font-size: 1.25rem; font-weight: 700; margin: 0.7em 0 0.35em; }
        .ProseMirror h3 { font-size: 1.1rem; font-weight: 700; margin: 0.6em 0 0.3em; }
        .ProseMirror h4 { font-size: 1rem; font-weight: 700; margin: 0.5em 0 0.25em; }
        .ProseMirror mark { border-radius: 2px; padding: 0 0.15em; }
      `}</style>
    </div>
  );
}
