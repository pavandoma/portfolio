<?php
// The only door that accepts changes to the learning log. The .htaccess in this
// folder asks the host for a username and password before this file runs, and
// progress.php then asks for the passphrase on top of that.
define('PROGRESS_WRITABLE', true);
require __DIR__ . '/../../api/progress.php';
