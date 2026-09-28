import hljs from 'highlight.js/lib/core'

import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import csharp from 'highlight.js/lib/languages/csharp'
import css from 'highlight.js/lib/languages/css'
import diff from 'highlight.js/lib/languages/diff'
import dockerfile from 'highlight.js/lib/languages/dockerfile'
import go from 'highlight.js/lib/languages/go'
import ini from 'highlight.js/lib/languages/ini'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import kotlin from 'highlight.js/lib/languages/kotlin'
import less from 'highlight.js/lib/languages/less'
import lua from 'highlight.js/lib/languages/lua'
import makefile from 'highlight.js/lib/languages/makefile'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'
import ruby from 'highlight.js/lib/languages/ruby'
import rust from 'highlight.js/lib/languages/rust'
import scss from 'highlight.js/lib/languages/scss'
import shell from 'highlight.js/lib/languages/shell'
import sql from 'highlight.js/lib/languages/sql'
import swift from 'highlight.js/lib/languages/swift'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

// A curated set keeps the bundle small; the backend only ever stores a
// Pygments language name, and these cover the common cases.
const LANGUAGES: Record<string, Parameters<typeof hljs.registerLanguage>[1]> = {
  bash,
  c,
  cpp,
  csharp,
  css,
  diff,
  dockerfile,
  go,
  ini,
  java,
  javascript,
  json,
  kotlin,
  less,
  lua,
  makefile,
  markdown,
  php,
  plaintext,
  python,
  ruby,
  rust,
  scss,
  shell,
  sql,
  swift,
  typescript,
  xml,
  yaml,
}

for (const [name, definition] of Object.entries(LANGUAGES)) {
  hljs.registerLanguage(name, definition)
}

/**
 * Pygments display names -> highlight.js ids. The backend stores names like
 * "Python" or "C++" rather than markdown fence tags.
 */
const NAME_ALIASES: Record<string, string> = {
  python: 'python',
  javascript: 'javascript',
  typescript: 'typescript',
  jsx: 'javascript',
  tsx: 'typescript',
  bash: 'bash',
  sh: 'bash',
  shell: 'bash',
  'shell-session': 'bash',
  console: 'bash',
  json: 'json',
  yaml: 'yaml',
  html: 'xml',
  xml: 'xml',
  css: 'css',
  scss: 'scss',
  sass: 'scss',
  less: 'less',
  go: 'go',
  golang: 'go',
  rust: 'rust',
  rs: 'rust',
  java: 'java',
  kotlin: 'kotlin',
  swift: 'swift',
  c: 'c',
  'c++': 'cpp',
  cpp: 'cpp',
  'c#': 'csharp',
  csharp: 'csharp',
  ruby: 'ruby',
  rb: 'ruby',
  php: 'php',
  lua: 'lua',
  sql: 'sql',
  markdown: 'markdown',
  md: 'markdown',
  dockerfile: 'dockerfile',
  makefile: 'makefile',
  ini: 'ini',
  toml: 'ini',
  diff: 'diff',
  patch: 'diff',
}

export function resolveLanguage(name: string | undefined, fallback?: string): string {
  if (!name) return fallback ?? 'plaintext'
  const key = name.toLowerCase().trim()
  return NAME_ALIASES[key] ?? (hljs.getLanguage(key) ? key : (fallback ?? 'plaintext'))
}

/**
 * Highlight line by line so each rendered row can carry its own gutter number.
 * Multi-line constructs (block comments, template literals) lose continuity
 * across the boundary, which is an acceptable trade for exact line alignment.
 */
export function highlightLines(code: string, language: string): string[] {
  const lines = code.replace(/\n$/, '').split('\n')
  return lines.map((line) => {
    if (line.trim() === '') return ''
    const result = hljs.highlight(line, { language, ignoreIllegals: true })
    return result.value
  })
}
