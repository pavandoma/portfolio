<?php
// The only door that accepts changes to the learning log. progress.php checks
// the passphrase and the per-visitor attempt limit before it writes anything.
define('PROGRESS_WRITABLE', true);
require __DIR__ . '/../../api/progress.php';
