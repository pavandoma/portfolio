import { agentProfile } from "@/content/prototype";

// Written to out/api/agent-profile.json at build time; public/api/mcp.php
// serves it to AI agents, so the agent and the site share one source.
export const dynamic = "force-static";

export function GET() {
  return Response.json(agentProfile());
}
