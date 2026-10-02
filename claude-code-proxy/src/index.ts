export default {
  async fetch(request: Request): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "*"
        }
      });
    }

    const url = new URL(request.url);
    const targetUrl = "https://seekai.cc" + url.pathname;
    const newRequest = new Request(targetUrl, request);
    
    // پاکسازی هدرهای کلاینت که باعث ارور ۴۰۱ می‌شدند
    newRequest.headers.delete("host");
    newRequest.headers.delete("x-api-key");
    newRequest.headers.delete("authorization");
    
    // کلید هاردکد شده با دسترسی کامل به مدل‌ها
    const apiKey = "sk-U5LHfhnfx6UDt7p6XrZeKB8v3a3Mvk2B1EVHhNu8vogyS1eb";
    
    newRequest.headers.set("x-api-key", apiKey);
    newRequest.headers.set("anthropic-version", "2023-06-01");

    try {
      const response = await fetch(newRequest);
      return new Response(response.body, {
        status: response.status,
        headers: {
          ...Object.fromEntries(response.headers),
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive"
        }
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: "Worker upstream error" }), { status: 502 });
    }
  }
};
