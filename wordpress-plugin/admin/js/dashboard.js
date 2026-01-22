/**
 * Siloq Dashboard JavaScript
 * Handles dashboard interactions and auto-refresh
 */

(function($) {
    'use strict';

    $(document).ready(function() {

        /**
         * Tab Navigation
         */
        $('.nav-tab').on('click', function(e) {
            e.preventDefault();

            var target = $(this).attr('href');

            // Update tabs
            $('.nav-tab').removeClass('nav-tab-active');
            $(this).addClass('nav-tab-active');

            // Update content
            $('.siloq-tab-content').hide();
            $(target).show();
        });

        /**
         * Retry Operation Button
         */
        $(document).on('click', '.siloq-retry-btn', function(e) {
            e.preventDefault();

            var $button = $(this);
            var queueId = $button.data('queue-id');

            if (!confirm('Retry this operation?')) {
                return;
            }

            $button.prop('disabled', true).text('Retrying...');

            $.ajax({
                url: siloqDashboard.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_retry_operation',
                    queue_id: queueId,
                    nonce: siloqDashboard.nonce
                },
                success: function(response) {
                    if (response.success) {
                        alert(response.data.message);
                        location.reload();
                    } else {
                        alert('Error: ' + response.data.message);
                        $button.prop('disabled', false).text('Retry');
                    }
                },
                error: function() {
                    alert('Failed to retry operation. Please try again.');
                    $button.prop('disabled', false).text('Retry');
                }
            });
        });

        /**
         * Clear Queue Button
         */
        $('.siloq-clear-queue-btn').on('click', function(e) {
            e.preventDefault();

            if (!confirm('Clear all completed items from the queue?')) {
                return;
            }

            var $button = $(this);
            $button.prop('disabled', true).text('Clearing...');

            $.ajax({
                url: siloqDashboard.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_clear_queue',
                    nonce: siloqDashboard.nonce
                },
                success: function(response) {
                    if (response.success) {
                        alert(response.data.message);
                        location.reload();
                    } else {
                        alert('Error: ' + response.data.message);
                        $button.prop('disabled', false).text('Clear Completed Items');
                    }
                },
                error: function() {
                    alert('Failed to clear queue. Please try again.');
                    $button.prop('disabled', false).text('Clear Completed Items');
                }
            });
        });

        /**
         * Trigger Cron Job Button
         */
        $(document).on('click', '.siloq-trigger-cron-btn', function(e) {
            e.preventDefault();

            var $button = $(this);
            var hook = $button.data('hook');

            if (!confirm('Run this cron job now?')) {
                return;
            }

            $button.prop('disabled', true).text('Running...');

            $.ajax({
                url: siloqDashboard.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_trigger_cron',
                    hook: hook,
                    nonce: siloqDashboard.nonce
                },
                success: function(response) {
                    if (response.success) {
                        alert(response.data.message);
                        $button.prop('disabled', false).text('Run Now');
                    } else {
                        alert('Error: ' + response.data.message);
                        $button.prop('disabled', false).text('Run Now');
                    }
                },
                error: function() {
                    alert('Failed to run cron job. Please try again.');
                    $button.prop('disabled', false).text('Run Now');
                }
            });
        });

        /**
         * Sync All Pages Button
         */
        $('.siloq-sync-all-btn').on('click', function(e) {
            e.preventDefault();

            if (!confirm('Sync all pages to Siloq? This may take a while.')) {
                return;
            }

            var $button = $(this);
            $button.prop('disabled', true).text('Syncing...');

            // Redirect to settings page which has the sync handler
            window.location.href = 'options-general.php?page=siloq-settings&action=manual_sync';
        });

        /**
         * Pull All Updates Button
         */
        $('.siloq-pull-all-btn').on('click', function(e) {
            e.preventDefault();

            if (!confirm('Pull all updates from Siloq? This will overwrite local changes.')) {
                return;
            }

            var $button = $(this);
            $button.prop('disabled', true).text('Pulling...');

            // Trigger pull cron job
            $.ajax({
                url: siloqDashboard.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_trigger_cron',
                    hook: 'siloq_pull_updates',
                    nonce: siloqDashboard.nonce
                },
                success: function(response) {
                    if (response.success) {
                        alert('Pull operation started. Check the activity log for results.');
                        setTimeout(function() {
                            location.reload();
                        }, 2000);
                    } else {
                        alert('Error: ' + response.data.message);
                        $button.prop('disabled', false).text('Pull All Updates');
                    }
                },
                error: function() {
                    alert('Failed to trigger pull. Please try again.');
                    $button.prop('disabled', false).text('Pull All Updates');
                }
            });
        });

        /**
         * Auto-refresh stats every 10 seconds
         */
        function refreshStats() {
            $.ajax({
                url: siloqDashboard.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_dashboard_stats',
                    nonce: siloqDashboard.nonce
                },
                success: function(response) {
                    if (response.success) {
                        updateStatCards(response.data);
                    }
                }
            });
        }

        /**
         * Update stat cards with new data
         */
        function updateStatCards(stats) {
            // Update pending count
            $('.siloq-stats-grid .siloq-stat-card:eq(0) h3').text(stats.pending);

            // Update completed count
            $('.siloq-stats-grid .siloq-stat-card:eq(1) h3').text(stats.completed);

            // Update failed count
            $('.siloq-stats-grid .siloq-stat-card:eq(2) h3').text(stats.failed);

            // Update success rate
            var successRate = stats.completed > 0
                ? Math.round((stats.completed / (stats.completed + stats.failed)) * 100)
                : 0;
            $('.siloq-stats-grid .siloq-stat-card:eq(3) h3').text(successRate + '%');
        }

        // Start auto-refresh
        setInterval(refreshStats, 10000); // Every 10 seconds

        /**
         * Highlight processing items
         */
        setInterval(function() {
            $('.siloq-status-processing').parent().parent().addClass('siloq-processing-highlight');
            setTimeout(function() {
                $('.siloq-processing-highlight').removeClass('siloq-processing-highlight');
            }, 500);
        }, 2000);

    });

})(jQuery);
