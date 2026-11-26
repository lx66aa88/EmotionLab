/** Read complete NDJSON events, including UTF-8 characters split across packets. */
export async function* analysisEvents(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let complete = false;
  try {
    while (!complete) {
      const { value, done } = await reader.read();
      complete = done;
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (line.trim()) yield JSON.parse(line);
      }
    }
    if (buffer.trim()) yield JSON.parse(buffer);
  } finally {
    if (!complete) await reader.cancel();
    reader.releaseLock();
  }
}
