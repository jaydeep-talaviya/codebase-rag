const EXTENSION_LANGUAGES: Record<string, string> = {
  py: 'Python',
  pyi: 'Python',
  js: 'JavaScript',
  mjs: 'JavaScript',
  cjs: 'JavaScript',
  jsx: 'JavaScript',
  ts: 'TypeScript',
  tsx: 'TypeScript',
  rb: 'Ruby',
  go: 'Go',
  rs: 'Rust',
  java: 'Java',
  kt: 'Kotlin',
  swift: 'Swift',
  c: 'C',
  h: 'C',
  cc: 'C++',
  cpp: 'C++',
  cxx: 'C++',
  hpp: 'C++',
  cs: 'C#',
  php: 'PHP',
  sh: 'Bash',
  bash: 'Bash',
  zsh: 'Bash',
  sql: 'SQL',
  json: 'JSON',
  yml: 'YAML',
  yaml: 'YAML',
  toml: 'TOML',
  md: 'Markdown',
  html: 'HTML',
  css: 'CSS',
  scss: 'SCSS',
  vue: 'Vue',
  svelte: 'Svelte',
  lua: 'Lua',
  pl: 'Perl',
  r: 'R',
  dart: 'Dart',
  ex: 'Elixir',
  exs: 'Elixir',
  scala: 'Scala',
  gradle: 'Gradle',
  dockerfile: 'Dockerfile',
  proto: 'Protocol Buffer',
}

/**
 * The API may omit a language for a source. Deriving it from the file
 * extension gives the code viewer something to highlight with.
 */
export function inferLanguageFromPath(filePath: string): string | undefined {
  const fileName = filePath.split('/').pop() ?? ''
  const dot = fileName.lastIndexOf('.')
  if (dot === -1 || dot === fileName.length - 1) {
    return fileName === 'Dockerfile' || fileName === 'Makefile' ? fileName : undefined
  }
  return EXTENSION_LANGUAGES[fileName.slice(dot + 1).toLowerCase()]
}
