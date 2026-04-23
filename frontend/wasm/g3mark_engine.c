#include <ctype.h>
#include <emscripten/emscripten.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  char *data;
  size_t length;
  size_t capacity;
} StringBuilder;

typedef struct {
  bool in_list;
  bool in_code_block;
  bool in_paragraph;
} MarkdownState;

static char *dup_string(const char *text) {
  size_t len = strlen(text);
  char *copy = (char *)malloc(len + 1);
  memcpy(copy, text, len + 1);
  return copy;
}

static void sb_init(StringBuilder *sb) {
  sb->capacity = 4096;
  sb->length = 0;
  sb->data = (char *)malloc(sb->capacity);
  sb->data[0] = '\0';
}

static void sb_ensure(StringBuilder *sb, size_t extra) {
  size_t needed = sb->length + extra + 1;
  if (needed <= sb->capacity) return;
  while (sb->capacity < needed) {
    sb->capacity *= 2;
  }
  sb->data = (char *)realloc(sb->data, sb->capacity);
}

static void sb_append(StringBuilder *sb, const char *text) {
  size_t len = strlen(text);
  sb_ensure(sb, len);
  memcpy(sb->data + sb->length, text, len);
  sb->length += len;
  sb->data[sb->length] = '\0';
}

static void sb_append_n(StringBuilder *sb, const char *text, size_t len) {
  sb_ensure(sb, len);
  memcpy(sb->data + sb->length, text, len);
  sb->length += len;
  sb->data[sb->length] = '\0';
}

static void sb_appendf(StringBuilder *sb, const char *fmt, ...) {
  va_list args;
  va_start(args, fmt);
  va_list args_copy;
  va_copy(args_copy, args);
  int needed = vsnprintf(NULL, 0, fmt, args_copy);
  va_end(args_copy);
  if (needed < 0) {
    va_end(args);
    return;
  }
  sb_ensure(sb, (size_t)needed);
  vsnprintf(sb->data + sb->length, sb->capacity - sb->length, fmt, args);
  sb->length += (size_t)needed;
  va_end(args);
}

static void append_escaped(StringBuilder *sb, const char *text) {
  while (*text) {
    switch (*text) {
      case '&': sb_append(sb, "&amp;"); break;
      case '<': sb_append(sb, "&lt;"); break;
      case '>': sb_append(sb, "&gt;"); break;
      case '"': sb_append(sb, "&quot;"); break;
      default: sb_append_n(sb, text, 1); break;
    }
    text++;
  }
}

static void append_inline_markup(StringBuilder *sb, const char *text) {
  bool in_code = false;
  while (*text) {
    if (*text == '`') {
      sb_append(sb, in_code ? "</code>" : "<code>");
      in_code = !in_code;
      text++;
      continue;
    }
    switch (*text) {
      case '&': sb_append(sb, "&amp;"); break;
      case '<': sb_append(sb, "&lt;"); break;
      case '>': sb_append(sb, "&gt;"); break;
      default: sb_append_n(sb, text, 1); break;
    }
    text++;
  }
  if (in_code) sb_append(sb, "</code>");
}

static char *trim_left(char *line) {
  while (*line && isspace((unsigned char)*line)) line++;
  return line;
}

static void close_markdown_blocks(StringBuilder *sb, MarkdownState *state) {
  if (state->in_paragraph) {
    sb_append(sb, "</p>");
    state->in_paragraph = false;
  }
  if (state->in_list) {
    sb_append(sb, "</ul>");
    state->in_list = false;
  }
}

EMSCRIPTEN_KEEPALIVE
char *render_markdown(const char *input) {
  if (!input) {
    char *empty = (char *)malloc(1);
    empty[0] = '\0';
    return empty;
  }

  StringBuilder out;
  sb_init(&out);
  MarkdownState state = { false, false, false };
  char *copy = dup_string(input);
  char *context = NULL;
  char *line = strtok_r(copy, "\n", &context);

  sb_append(&out, "<div class=\"g3mark-document\">");
  while (line) {
    char *trimmed = trim_left(line);

    if (strncmp(trimmed, "```", 3) == 0) {
      close_markdown_blocks(&out, &state);
      if (!state.in_code_block) {
        char *lang = trimmed + 3;
        while (*lang && isspace((unsigned char)*lang)) lang++;
        sb_appendf(
          &out,
          "<pre class=\"g3mark-code-block\"><div class=\"g3mark-code-meta\">%s</div><code>",
          *lang ? lang : "text"
        );
      } else {
        sb_append(&out, "</code></pre>");
      }
      state.in_code_block = !state.in_code_block;
      line = strtok_r(NULL, "\n", &context);
      continue;
    }

    if (state.in_code_block) {
      append_escaped(&out, line);
      sb_append(&out, "\n");
      line = strtok_r(NULL, "\n", &context);
      continue;
    }

    if (*trimmed == '\0') {
      close_markdown_blocks(&out, &state);
      line = strtok_r(NULL, "\n", &context);
      continue;
    }

    if (trimmed[0] == '#' ) {
      close_markdown_blocks(&out, &state);
      int level = 0;
      while (trimmed[level] == '#' && level < 6) level++;
      while (trimmed[level] == ' ') level++;
      sb_appendf(&out, "<h%d>", level);
      append_inline_markup(&out, trimmed + level);
      sb_appendf(&out, "</h%d>", level);
      line = strtok_r(NULL, "\n", &context);
      continue;
    }

    if ((trimmed[0] == '-' || trimmed[0] == '*') && trimmed[1] == ' ') {
      if (state.in_paragraph) {
        sb_append(&out, "</p>");
        state.in_paragraph = false;
      }
      if (!state.in_list) {
        sb_append(&out, "<ul>");
        state.in_list = true;
      }
      sb_append(&out, "<li>");
      append_inline_markup(&out, trimmed + 2);
      sb_append(&out, "</li>");
      line = strtok_r(NULL, "\n", &context);
      continue;
    }

    if (!state.in_paragraph) {
      if (state.in_list) {
        sb_append(&out, "</ul>");
        state.in_list = false;
      }
      sb_append(&out, "<p>");
      state.in_paragraph = true;
    } else {
      sb_append(&out, " ");
    }
    append_inline_markup(&out, trimmed);
    line = strtok_r(NULL, "\n", &context);
  }

  if (state.in_code_block) sb_append(&out, "</code></pre>");
  close_markdown_blocks(&out, &state);
  sb_append(&out, "</div>");

  free(copy);
  return out.data;
}

static void split_lines(const char *text, char ***lines_out, int *count_out) {
  char *copy = dup_string(text ? text : "");
  int capacity = 32;
  int count = 0;
  char **lines = (char **)malloc((size_t)capacity * sizeof(char *));
  char *context = NULL;
  char *line = strtok_r(copy, "\n", &context);

  while (line) {
    if (count == capacity) {
      capacity *= 2;
      lines = (char **)realloc(lines, (size_t)capacity * sizeof(char *));
    }
    lines[count++] = dup_string(line);
    line = strtok_r(NULL, "\n", &context);
  }

  if (count == 0) {
    lines[count++] = dup_string("");
  }

  free(copy);
  *lines_out = lines;
  *count_out = count;
}

static void free_lines(char **lines, int count) {
  for (int i = 0; i < count; i++) {
    free(lines[i]);
  }
  free(lines);
}

static int max_int(int a, int b) {
  return a > b ? a : b;
}

EMSCRIPTEN_KEEPALIVE
char *render_diff_stats(const char *original, const char *modified) {
  char **left = NULL;
  char **right = NULL;
  int left_count = 0;
  int right_count = 0;
  split_lines(original, &left, &left_count);
  split_lines(modified, &right, &right_count);

  int added = 0;
  int removed = 0;
  int changed = 0;
  int shared = 0;
  int max_lines = max_int(left_count, right_count);

  for (int i = 0; i < max_lines; i++) {
    const char *l = i < left_count ? left[i] : NULL;
    const char *r = i < right_count ? right[i] : NULL;
    if (l && r) {
      if (strcmp(l, r) == 0) {
        shared++;
      } else {
        changed++;
      }
    } else if (l) {
      removed++;
    } else {
      added++;
    }
  }

  StringBuilder out;
  sb_init(&out);
  sb_appendf(
    &out,
    "{\"added\":%d,\"removed\":%d,\"changed\":%d,\"shared\":%d}",
    added,
    removed,
    changed,
    shared
  );

  free_lines(left, left_count);
  free_lines(right, right_count);
  return out.data;
}

EMSCRIPTEN_KEEPALIVE
char *render_diff(const char *original, const char *modified) {
  char **left = NULL;
  char **right = NULL;
  int left_count = 0;
  int right_count = 0;
  split_lines(original, &left, &left_count);
  split_lines(modified, &right, &right_count);

  StringBuilder out;
  sb_init(&out);
  sb_append(&out, "<div class=\"g3mark-diff\">");

  int max_lines = max_int(left_count, right_count);
  for (int i = 0; i < max_lines; i++) {
    const char *l = i < left_count ? left[i] : NULL;
    const char *r = i < right_count ? right[i] : NULL;
    const char *klass = "same";
    const char *marker = " ";

    if (l && r) {
      if (strcmp(l, r) != 0) {
        klass = "changed";
        marker = "~";
      }
    } else if (l) {
      klass = "removed";
      marker = "-";
    } else {
      klass = "added";
      marker = "+";
    }

    sb_appendf(
      &out,
      "<div class=\"g3mark-diff-line g3mark-diff-line--%s\"><span class=\"g3mark-diff-marker\">%s</span><span class=\"g3mark-diff-original\">",
      klass,
      marker
    );
    append_escaped(&out, l ? l : "");
    sb_append(&out, "</span><span class=\"g3mark-diff-arrow\">→</span><span class=\"g3mark-diff-modified\">");
    append_escaped(&out, r ? r : "");
    sb_append(&out, "</span></div>");
  }

  sb_append(&out, "</div>");
  free_lines(left, left_count);
  free_lines(right, right_count);
  return out.data;
}
