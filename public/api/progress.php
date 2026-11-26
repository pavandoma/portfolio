<?php
/**
 * Learning-log progress for the portfolio.
 *
 *   GET   → {"done": {"<item id>": "YYYY-MM-DD", ...}, "updated": "<ISO time>"}
 *   POST  → body {"passphrase": "...", "id": "<item id>", "done": true|false}
 *           or    {"passphrase": "...", "check": true}  (just verify the passphrase)
 *
 * Anyone may read. Only someone who knows the passphrase may change anything.
 * State and credentials live in a folder OUTSIDE the web root (a sibling of
 * public_html), so a redeploy of the site never overwrites them and nobody can
 * download them.
 *
 * The passphrase is never stored: auth.php holds a salted PBKDF2 hash, written
 * by scripts/make-auth.mjs on the owner's own machine.
 */

declare(strict_types=1);

const MAX_ITEMS        = 600;
const MAX_FAILURES     = 8;      // wrong passphrases per client...
const FAILURE_WINDOW_S = 900;    // ...within fifteen minutes
const PBKDF2_ROUNDS    = 200000;

function data_dir(): string
{
    $override = getenv('PORTFOLIO_DATA_DIR');
    if (is_string($override) && $override !== '') {
        return rtrim($override, '/\\');
    }
    // portfolio-data sits beside public_html, wherever the site is served from:
    //   .../domains/<domain>/public_html          (site at the domain root)
    //   .../domains/<domain>/public_html/<site>   (site on a subdomain folder)
    // both resolve to .../domains/<domain>/portfolio-data.
    $dir = (string) ($_SERVER['DOCUMENT_ROOT'] ?? __DIR__);
    for ($probe = $dir; $probe !== dirname($probe); $probe = dirname($probe)) {
        if (basename($probe) === 'public_html') {
            return dirname($probe) . '/portfolio-data';
        }
    }
    return dirname($dir, 2) . '/portfolio-data';
}

function respond(int $status, array $body): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($body, JSON_UNESCAPED_SLASHES);
}

/** Read a JSON file under an exclusive lock; a missing or broken file is `$default`. */
function read_json(string $path, array $default): array
{
    if (!is_file($path)) {
        return $default;
    }
    $raw = @file_get_contents($path);
    $decoded = is_string($raw) ? json_decode($raw, true) : null;
    return is_array($decoded) ? $decoded : $default;
}

/** Write atomically: temp file in the same folder, then rename over the target. */
function write_json(string $path, array $value): bool
{
    $tmp = $path . '.' . bin2hex(random_bytes(4)) . '.tmp';
    $ok = @file_put_contents($tmp, json_encode($value, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT), LOCK_EX) !== false;
    if (!$ok) {
        return false;
    }
    if (!@rename($tmp, $path)) {
        @unlink($tmp);
        return false;
    }
    return true;
}

function client_key(): string
{
    return hash('sha256', (string) ($_SERVER['REMOTE_ADDR'] ?? 'unknown'));
}

function too_many_failures(string $dir): bool
{
    $log = read_json($dir . '/attempts.json', []);
    $now = time();
    $recent = array_filter((array) ($log[client_key()] ?? []), static fn ($t) => is_int($t) && $now - $t < FAILURE_WINDOW_S);
    return count($recent) >= MAX_FAILURES;
}

function record_failure(string $dir): void
{
    $path = $dir . '/attempts.json';
    $log = read_json($path, []);
    $now = time();
    $key = client_key();
    $recent = array_values(array_filter((array) ($log[$key] ?? []), static fn ($t) => is_int($t) && $now - $t < FAILURE_WINDOW_S));
    $recent[] = $now;
    $log[$key] = $recent;
    // Forget clients that have been quiet, so the file cannot grow without bound.
    foreach ($log as $k => $times) {
        if (!is_array($times) || max($times ?: [0]) < $now - FAILURE_WINDOW_S) {
            unset($log[$k]);
        }
    }
    write_json($path, $log);
}

function passphrase_ok(string $dir, string $passphrase): bool
{
    $auth = @include $dir . '/auth.php';
    if (!is_array($auth) || !isset($auth['salt'], $auth['hash'], $auth['rounds'])) {
        return false;
    }
    $candidate = hash_pbkdf2('sha256', $passphrase, (string) $auth['salt'], (int) $auth['rounds'], 64);
    return hash_equals((string) $auth['hash'], $candidate);
}

function handle(): void
{
    $dir = data_dir();
    $statePath = $dir . '/progress.json';
    $method = (string) ($_SERVER['REQUEST_METHOD'] ?? 'GET');

    if ($method === 'GET') {
        $state = read_json($statePath, ['done' => [], 'updated' => null]);
        respond(200, ['done' => (object) ($state['done'] ?? []), 'updated' => $state['updated'] ?? null]);
        return;
    }

    // Changes are only accepted through learning/manage/save.php, which sits
    // behind the host's login. This public entry point is read-only.
    if ($method !== 'POST' || !defined('PROGRESS_WRITABLE')) {
        header('Allow: ' . (defined('PROGRESS_WRITABLE') ? 'GET, POST' : 'GET'));
        respond(405, ['error' => 'method_not_allowed']);
        return;
    }

    if (!is_dir($dir) && !@mkdir($dir, 0700, true)) {
        respond(500, ['error' => 'storage_unavailable']);
        return;
    }
    if (!is_file($dir . '/auth.php')) {
        respond(503, ['error' => 'not_configured']);
        return;
    }
    if (too_many_failures($dir)) {
        header('Retry-After: ' . FAILURE_WINDOW_S);
        respond(429, ['error' => 'too_many_attempts']);
        return;
    }

    $raw = $GLOBALS['__PROGRESS_BODY'] ?? file_get_contents('php://input');
    if (!is_string($raw) || strlen($raw) > 4096) {
        respond(413, ['error' => 'body_too_large']);
        return;
    }
    $body = json_decode($raw, true);
    if (!is_array($body)) {
        respond(400, ['error' => 'invalid_json']);
        return;
    }

    $passphrase = $body['passphrase'] ?? null;
    if (!is_string($passphrase) || $passphrase === '' || strlen($passphrase) > 256 || !passphrase_ok($dir, $passphrase)) {
        record_failure($dir);
        respond(401, ['error' => 'unauthorized']);
        return;
    }

    if (($body['check'] ?? false) === true) {
        respond(200, ['ok' => true]);
        return;
    }

    $id = $body['id'] ?? null;
    $done = $body['done'] ?? null;
    if (!is_string($id) || !preg_match('/^[a-z0-9][a-z0-9-]{0,79}$/', $id) || !is_bool($done)) {
        respond(400, ['error' => 'invalid_request']);
        return;
    }

    // Serialise writers so two quick ticks cannot overwrite each other.
    $lock = fopen($dir . '/progress.lock', 'c');
    if ($lock === false || !flock($lock, LOCK_EX)) {
        respond(500, ['error' => 'lock_failed']);
        return;
    }
    try {
        $state = read_json($statePath, ['done' => [], 'updated' => null]);
        $map = is_array($state['done'] ?? null) ? $state['done'] : [];

        if ($done) {
            if (!isset($map[$id]) && count($map) >= MAX_ITEMS) {
                respond(409, ['error' => 'too_many_items']);
                return;
            }
            // A backfill date is allowed (ticking something finished last week);
            // anything malformed or in the future falls back to today.
            $tz = new DateTimeZone('America/New_York');
            $today = new DateTimeImmutable('today', $tz);
            $date = $today->format('Y-m-d');
            $asked = $body['date'] ?? null;
            if (is_string($asked) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $asked)) {
                $parsed = DateTimeImmutable::createFromFormat('!Y-m-d', $asked, $tz);
                if ($parsed !== false && $parsed->format('Y-m-d') === $asked && $parsed <= $today) {
                    $date = $asked;
                }
            }
            $map[$id] = $date;
        } else {
            unset($map[$id]);
        }

        $state = ['done' => $map, 'updated' => gmdate('c')];
        if (!write_json($statePath, $state)) {
            respond(500, ['error' => 'write_failed']);
            return;
        }
        respond(200, ['done' => (object) $map, 'updated' => $state['updated']]);
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

// Guard so the file can also be included by a test harness without running.
if (!defined('PROGRESS_NO_AUTORUN')) {
    handle();
}
