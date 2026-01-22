/**
 * Siloq Metaboxes JavaScript
 * Handles interactions for post edit screen metaboxes
 */

(function($) {
    'use strict';

    $(document).ready(function() {

        /**
         * Sync Now Button
         */
        $(document).on('click', '.siloq-sync-now-btn', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $message = $('#siloq-sync-message');
            var postId = $('.siloq-sync-status-box').data('post-id');

            $button.prop('disabled', true).text('Syncing...');
            $message.html('');

            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_sync_now',
                    post_id: postId,
                    nonce: siloqMetaboxes.nonce
                },
                success: function(response) {
                    if (response.success) {
                        $message.html('<div class="notice notice-success inline"><p>' + response.data.message + '</p></div>');
                        // Reload page after short delay
                        setTimeout(function() {
                            location.reload();
                        }, 1500);
                    } else {
                        $message.html('<div class="notice notice-error inline"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Sync Now');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error inline"><p>Failed to sync. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Sync Now');
                }
            });
        });

        /**
         * Check Gates Button
         */
        $(document).on('click', '.siloq-check-gates-btn', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $message = $('#siloq-gates-message');
            var $container = $('.siloq-gates-box');
            var postId = $container.data('post-id');

            $button.prop('disabled', true).text('Checking...');
            $message.html('');

            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_check_gates',
                    post_id: postId,
                    nonce: siloqMetaboxes.nonce
                },
                success: function(response) {
                    if (response.success) {
                        // Replace gate results HTML
                        $container.find('.siloq-gate-results, p').first().replaceWith(response.data.html);
                        $message.html('<div class="notice notice-success inline"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Check Gates');

                        // Show publish button if all passed
                        if (response.data.results.all_passed) {
                            if (!$('.siloq-publish-to-siloq-btn').length) {
                                $button.after(' <button type="button" class="button button-primary siloq-publish-to-siloq-btn">Publish to Siloq</button>');
                            }
                        }
                    } else {
                        $message.html('<div class="notice notice-error inline"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Check Gates');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error inline"><p>Failed to check gates. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Check Gates');
                }
            });
        });

        /**
         * Publish to Siloq Button
         */
        $(document).on('click', '.siloq-publish-to-siloq-btn', function(e) {
            e.preventDefault();

            if (!confirm('Publish this content to Siloq? All lifecycle gates have passed.')) {
                return;
            }

            var $button = $(this);
            var $message = $('#siloq-gates-message');
            var postId = $('.siloq-gates-box').data('post-id');

            $button.prop('disabled', true).text('Publishing...');
            $message.html('');

            // For now, just sync - full publish implementation would call publish API
            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_sync_now',
                    post_id: postId,
                    nonce: siloqMetaboxes.nonce
                },
                success: function(response) {
                    if (response.success) {
                        $message.html('<div class="notice notice-success inline"><p>Published to Siloq successfully!</p></div>');
                        $button.prop('disabled', false).text('Publish to Siloq');
                    } else {
                        $message.html('<div class="notice notice-error inline"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Publish to Siloq');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error inline"><p>Failed to publish. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Publish to Siloq');
                }
            });
        });

        /**
         * Refresh Schema Button
         */
        $(document).on('click', '.siloq-refresh-schema-btn', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $message = $('#siloq-schema-message');
            var postId = $('.siloq-schema-box').data('post-id');

            $button.prop('disabled', true).text('Refreshing...');
            $message.html('');

            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_refresh_schema',
                    post_id: postId,
                    nonce: siloqMetaboxes.nonce
                },
                success: function(response) {
                    if (response.success) {
                        $message.html('<div class="notice notice-success inline"><p>' + response.data.message + '</p></div>');
                        // Reload page to show new schema
                        setTimeout(function() {
                            location.reload();
                        }, 1000);
                    } else {
                        $message.html('<div class="notice notice-error inline"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Refresh Schema');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error inline"><p>Failed to refresh schema. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Refresh Schema');
                }
            });
        });

        /**
         * Copy Schema to Clipboard
         */
        $(document).on('click', '.siloq-copy-schema-btn', function(e) {
            e.preventDefault();

            var schemaText = $('.siloq-schema-preview pre').text();

            if (navigator.clipboard) {
                navigator.clipboard.writeText(schemaText).then(function() {
                    alert('Schema copied to clipboard!');
                }).catch(function() {
                    alert('Failed to copy schema to clipboard.');
                });
            } else {
                // Fallback for older browsers
                var $temp = $('<textarea>');
                $('body').append($temp);
                $temp.val(schemaText).select();
                document.execCommand('copy');
                $temp.remove();
                alert('Schema copied to clipboard!');
            }
        });

        /**
         * Generate Content Button (from generation UI)
         */
        $(document).on('click', '#siloq-generate-content-btn', function(e) {
            e.preventDefault();

            if (!confirm('Generate AI-powered content for this page? This may overwrite existing content if selected.')) {
                return;
            }

            var $button = $(this);
            var $message = $('#siloq-generation-message');
            var postId = $('.siloq-generation-ui').data('post-id');
            var overwrite = $('#siloq-gen-overwrite').is(':checked');
            var nonce = $('#siloq_generation_nonce').val();

            $button.prop('disabled', true).text('Starting Generation...');
            $message.html('');

            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_generate_content',
                    post_id: postId,
                    overwrite: overwrite,
                    nonce: nonce
                },
                success: function(response) {
                    if (response.success) {
                        $message.html('<div class="notice notice-success inline"><p>' + response.data.message + '</p></div>');
                        // Reload page to show job status
                        setTimeout(function() {
                            location.reload();
                        }, 1500);
                    } else {
                        $message.html('<div class="notice notice-error inline"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Generate Content');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error inline"><p>Failed to start generation. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Generate Content');
                }
            });
        });

        /**
         * Poll job status if generation is in progress
         */
        var $jobStatus = $('.siloq-job-status');
        if ($jobStatus.length && $jobStatus.data('job-id')) {
            var pollInterval = setInterval(function() {
                var postId = $('.siloq-generation-ui').data('post-id');

                $.ajax({
                    url: siloqMetaboxes.ajaxurl,
                    type: 'POST',
                    data: {
                        action: 'siloq_poll_job_status',
                        post_id: postId,
                        nonce: siloqMetaboxes.nonce
                    },
                    success: function(response) {
                        if (response.success && response.data.job) {
                            var job = response.data.job;
                            var status = job.status;

                            // Update progress bar
                            if (job.progress_percentage) {
                                $('.siloq-progress-bar-fill').css('width', job.progress_percentage + '%');
                                $('.siloq-progress-bar-fill').next('p').text(job.progress_percentage + '% complete');
                            }

                            // If completed or failed, reload page
                            if (status === 'completed' || status === 'failed') {
                                clearInterval(pollInterval);
                                setTimeout(function() {
                                    location.reload();
                                }, 2000);
                            }
                        }
                    }
                });
            }, 5000); // Poll every 5 seconds
        }

        /**
         * Cancel Generation Button
         */
        $(document).on('click', '.siloq-cancel-generation-btn', function(e) {
            e.preventDefault();

            if (!confirm('Cancel content generation?')) {
                return;
            }

            var postId = $('.siloq-generation-ui').data('post-id');

            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_cancel_generation',
                    post_id: postId,
                    nonce: siloqMetaboxes.nonce
                },
                success: function(response) {
                    if (response.success) {
                        location.reload();
                    }
                }
            });
        });

        /**
         * Clear Job Button
         */
        $(document).on('click', '.siloq-clear-job-btn', function(e) {
            e.preventDefault();

            var postId = $('.siloq-generation-ui').data('post-id');

            $.ajax({
                url: siloqMetaboxes.ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_cancel_generation',
                    post_id: postId,
                    nonce: siloqMetaboxes.nonce
                },
                success: function(response) {
                    if (response.success) {
                        location.reload();
                    }
                }
            });
        });

    });

})(jQuery);
