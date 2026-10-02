interface Env {
  NVIDIA_API_KEY: string;
}

const NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Health check
    if (request.method === "GET" && url.pathname === "/") {
      return Response.json({
        status: "ok",
        service: "nvidia-codex-proxy",
      });
    }

    // OpenAI-compatible models endpoint
    if (request.method === "GET" && url.pathname === "/v1/models") {
      return Response.json({
        object: "list",
        data: [
          {
            id: "nvidia/nemotron-3-ultra-550b-a55b",
            object: "model",
            owned_by: "nvidia",
          },
        ],
      });
    }

    // Accept:
    // /v1/responses
    // /nvidia/v1/responses
    const isResponsesEndpoint =
      url.pathname === "/v1/responses" ||
      url.pathname === "/nvidia/v1/responses";

    if (request.method === "POST" && isResponsesEndpoint) {
      const body = await request.json();

      // Force the NVIDIA model
      body.model = "nvidia/nemotron-3-ultra-550b-a55b";

      const upstream = await fetch(
        `${NVIDIA_BASE_URL}/responses`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${env.NVIDIA_API_KEY}`,
          },
          body: JSON.stringify(body),
        },
      );

      return new Response(upstream.body, {
        status: upstream.status,
        headers: {
          "Content-Type":
            upstream.headers.get("Content-Type") ??
            "application/json",
          "Cache-Control": "no-cache",
        },
      });
    }

    return Response.json(
      {
        error: {
          message: "Endpoint not found",
          type: "invalid_request_error",
          path: url.pathname,
        },
      },
      { status: 404 },
    );
  },
} satisfies ExportedHandler<Env>;
