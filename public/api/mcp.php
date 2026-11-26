<?php
/**
 * "Add me to your agent": a read-only MCP server (Streamable HTTP transport,
 * stateless, JSON responses) that answers questions about Pavan.
 *
 *   claude mcp add -t http pavan https://voiyu.com/mcp
 *
 * (/mcp is rewritten to this file by .htaccess; /api/mcp.php works too.)
 *
 * The data is agent-profile.json beside this file, which `next build` writes
 * from src/content (see src/app/api/agent-profile.json/route.ts), so nothing
 * here needs editing when the portfolio content changes.
 *
 * Nothing is written, no secrets are involved, and no session is kept: every
 * POST carries one JSON-RPC message and gets one JSON reply.
 */

const SUPPORTED_VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Accept, Mcp-Session-Id, MCP-Protocol-Version');
header('Cache-Control: no-store');

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if ($method === 'OPTIONS') {
    http_response_code(204);
    exit;
}
if ($method !== 'POST') {
    // No server-to-client stream is offered; the spec asks for 405 here.
    header('Allow: POST, OPTIONS');
    http_response_code(405);
    exit;
}

/** Send one JSON-RPC response and stop. */
function reply($id, $result = null, $error = null)
{
    header('Content-Type: application/json');
    $msg = ['jsonrpc' => '2.0', 'id' => $id];
    if ($error !== null) {
        $msg['error'] = $error;
    } else {
        $msg['result'] = $result;
    }
    echo json_encode($msg, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

$raw = $GLOBALS['__MCP_BODY'] ?? file_get_contents('php://input');
$req = json_decode((string) $raw, true);
if (!is_array($req) || ($req['jsonrpc'] ?? null) !== '2.0' || !isset($req['method'])) {
    http_response_code(400);
    reply(null, null, ['code' => -32700, 'message' => 'Expected a single JSON-RPC 2.0 message']);
}

$id = $req['id'] ?? null;
$rpc = $req['method'];

// Notifications (no id) need no answer.
if (!array_key_exists('id', $req)) {
    http_response_code(202);
    exit;
}

$data = json_decode((string) @file_get_contents(__DIR__ . '/agent-profile.json'), true);
if (!is_array($data)) {
    reply($id, null, ['code' => -32603, 'message' => 'Profile data is unavailable']);
}

$tools = [
    'get_profile' => ['Who Pavan is: name, title, summary, focus areas, education and certifications.',
        fn () => [
            'name' => $data['name'], 'title' => $data['title'], 'summary' => $data['summary'],
            'focusAreas' => $data['focusAreas'], 'education' => $data['education'],
            'certifications' => $data['certifications'],
        ]],
    'get_projects' => ['Pavan\'s featured projects with their headline result, tech and GitHub link.',
        fn () => $data['projects']],
    'get_experience' => ['Pavan\'s work experience with the outcomes of each role.',
        fn () => $data['experience']],
    'get_skills' => ['Pavan\'s skills, grouped by area.',
        fn () => $data['skills']],
    'get_contact' => ['How to reach Pavan: email, LinkedIn, GitHub, portfolio and blog.',
        fn () => $data['contact']],
];

switch ($rpc) {
    case 'initialize':
        $asked = $req['params']['protocolVersion'] ?? '';
        reply($id, [
            'protocolVersion' => in_array($asked, SUPPORTED_VERSIONS, true) ? $asked : SUPPORTED_VERSIONS[0],
            'capabilities' => ['tools' => ['listChanged' => false]],
            'serverInfo' => ['name' => 'pavan-srinivas', 'version' => '1.0.0'],
            'instructions' => 'Read-only facts about Pavan Srinivas Doma, an AI/ML engineer. '
                . 'Call get_profile first, then the other tools for detail.',
        ]);

    case 'ping':
        reply($id, new stdClass());

    case 'tools/list':
        $list = [];
        foreach ($tools as $name => [$description]) {
            $list[] = [
                'name' => $name,
                'description' => $description,
                'inputSchema' => ['type' => 'object', 'properties' => new stdClass()],
                'annotations' => ['readOnlyHint' => true, 'openWorldHint' => false],
            ];
        }
        reply($id, ['tools' => $list]);

    case 'tools/call':
        $name = $req['params']['name'] ?? '';
        if (!isset($tools[$name])) {
            reply($id, null, ['code' => -32602, 'message' => "Unknown tool: $name"]);
        }
        $out = ($tools[$name][1])();
        reply($id, ['content' => [[
            'type' => 'text',
            'text' => json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        ]], 'isError' => false]);

    default:
        reply($id, null, ['code' => -32601, 'message' => "Method not found: $rpc"]);
}
