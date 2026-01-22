/**
 * Siloq Admin JavaScript
 * Handles API key management and settings page interactions
 */

(function($) {
    'use strict';

    $(document).ready(function() {

        /**
         * Generate API Key
         */
        $('#siloq-generate-api-key').on('click', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $message = $('#siloq-api-key-message');

            // Confirm action
            if (!confirm('Generate a new API key? This will be your primary authentication method with Siloq.')) {
                return;
            }

            $button.prop('disabled', true).text('Generating...');
            $message.html('');

            $.ajax({
                url: ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_generate_api_key',
                    nonce: wp.nonce_generate_api_key || wp.ajax_nonce
                },
                success: function(response) {
                    if (response.success) {
                        $message.html('<div class="notice notice-success"><p>' + response.data.message + '</p></div>');
                        // Reload page to show new key
                        setTimeout(function() {
                            location.reload();
                        }, 1500);
                    } else {
                        $message.html('<div class="notice notice-error"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Generate API Key');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error"><p>Failed to generate API key. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Generate API Key');
                }
            });
        });

        /**
         * Rotate API Key
         */
        $('#siloq-rotate-api-key').on('click', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $message = $('#siloq-api-key-message');

            // Confirm action
            if (!confirm('Rotate API key? This will generate a new key and revoke the current one. Make sure you update the key in Siloq backend as well.')) {
                return;
            }

            $button.prop('disabled', true).text('Rotating...');
            $message.html('');

            $.ajax({
                url: ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_rotate_api_key',
                    nonce: wp.nonce_rotate_api_key || wp.ajax_nonce,
                    reason: 'Manual rotation via WordPress plugin'
                },
                success: function(response) {
                    if (response.success) {
                        $message.html('<div class="notice notice-success"><p>' + response.data.message + '</p></div>');
                        // Reload page to show new key
                        setTimeout(function() {
                            location.reload();
                        }, 1500);
                    } else {
                        $message.html('<div class="notice notice-error"><p>' + response.data.message + '</p></div>');
                        $button.prop('disabled', false).text('Rotate API Key');
                    }
                },
                error: function() {
                    $message.html('<div class="notice notice-error"><p>Failed to rotate API key. Please try again.</p></div>');
                    $button.prop('disabled', false).text('Rotate API Key');
                }
            });
        });

        /**
         * Generate Webhook Secret
         */
        $('#siloq-generate-webhook-secret').on('click', function(e) {
            e.preventDefault();

            var $button = $(this);
            var $input = $('#siloq_webhook_secret');

            $button.prop('disabled', true).text('Generating...');

            $.ajax({
                url: ajaxurl,
                type: 'POST',
                data: {
                    action: 'siloq_generate_webhook_secret',
                    nonce: wp.nonce_generate_webhook_secret || wp.ajax_nonce
                },
                success: function(response) {
                    if (response.success) {
                        $input.val(response.data.secret);
                        $button.prop('disabled', false).text('Generate');

                        // Show success message
                        var $notice = $('<div class="notice notice-success is-dismissible"><p>' + response.data.message + '</p></div>');
                        $('.siloq-webhook-config').prepend($notice);
                        setTimeout(function() {
                            $notice.fadeOut();
                        }, 3000);
                    } else {
                        alert('Failed to generate webhook secret: ' + response.data.message);
                        $button.prop('disabled', false).text('Generate');
                    }
                },
                error: function() {
                    alert('Failed to generate webhook secret. Please try again.');
                    $button.prop('disabled', false).text('Generate');
                }
            });
        });

    });

})(jQuery);
