import { z } from "zod";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
    ListResourcesRequestSchema,
    ListResourceTemplatesRequestSchema,
    ListPromptsRequestSchema,
    InitializeRequestSchema,
    type CallToolRequest,
    type InitializeRequest,
} from "@modelcontextprotocol/sdk/types.js";
import { zodToJsonSchema } from "zod-to-json-schema";
import { getSystemInfo, getOSSpecificGuidance, getPathGuidance, getDevelopmentToolGuidance } from './utils/system-info.js';

// Get system information once at startup
const SYSTEM_INFO = getSystemInfo();
const OS_GUIDANCE = getOSSpecificGuidance(SYSTEM_INFO);
const DEV_TOOL_GUIDANCE = getDevelopmentToolGuidance(SYSTEM_INFO);
const PATH_GUIDANCE = `IMPORTANT: ${getPathGuidance(SYSTEM_INFO)} Relative paths may fail as they depend on the current working directory. Tilde paths (~/...) might not work in all contexts. Unless the user explicitly asks for relative paths, use absolute paths.`;

const CMD_PREFIX_DESCRIPTION = `This command can be referenced as "DC: ..." or "use Desktop Commander to ..." in your instructions.`;

import {
    StartProcessArgsSchema,
    ReadProcessOutputArgsSchema,
    InteractWithProcessArgsSchema,
    ForceTerminateArgsSchema,
    ListSessionsArgsSchema,
    KillProcessArgsSchema,
    ReadMultipleFilesArgsSchema,
    WriteFileArgsSchema,
    CreateDirectoryArgsSchema,
    ListDirectoryArgsSchema,
    MoveFileArgsSchema,
    GetFileInfoArgsSchema,
    GetConfigArgsSchema,
    SetConfigValueArgsSchema,
    ListProcessesArgsSchema,
    EditBlockArgsSchema,
    GetUsageStatsArgsSchema,
    GiveFeedbackArgsSchema,
    StartSearchArgsSchema,
    GetMoreSearchResultsArgsSchema,
    StopSearchArgsSchema,
    ListSearchesArgsSchema,
    GetPromptsArgsSchema,
} from './tools/schemas.js';
import { getConfig, setConfigValue } from './tools/config.js';
import { getUsageStats } from './tools/usage.js';
import { giveFeedbackToDesktopCommander } from './tools/feedback.js';
import { getPrompts } from './tools/prompts.js';
import { trackToolCall } from './utils/trackTools.js';
import { usageTracker } from './utils/usageTracker.js';
import { processDockerPrompt } from './utils/dockerPrompt.js';

import { VERSION } from './version.js';
import { capture, capture_call_tool } from "./utils/capture.js";
import { logToStderr, logger } from './utils/logger.js';

// Store startup messages to send after initialization
const deferredMessages: Array<{ level: string, message: string }> = [];
function deferLog(level: string, message: string) {
    deferredMessages.push({ level, message });
}

process.umask(0);
const ReadFileArgsSchema = z.object({
    path: z.string(),
    offset: z.number().optional().default(0),
    length: z.number().optional().default(1000),
});
// Function to flush deferred messages after initialization
export function flushDeferredMessages() {
    while (deferredMessages.length > 0) {
        const msg = deferredMessages.shift()!;
        logger.info(msg.message);
    }
}

export const server = new Server(
    {
        name: "desktop-commander",
        version: VERSION,
    },
    {
        capabilities: {
            tools: {},
            resources: {},  // Add empty resources capability
            prompts: {},    // Add empty prompts capability
            logging: {},    // Add logging capability for console redirection
        },
    },
);

// Add handler for resources/list method
server.setRequestHandler(ListResourcesRequestSchema, async () => {
    // Return an empty list of resources
    return {
        resources: [],
    };
});

// Add handler for prompts/list method
server.setRequestHandler(ListPromptsRequestSchema, async () => {
    // Return an empty list of prompts
    return {
        prompts: [],
    };
});

// Store current client info (simple variable)
let currentClient = { name: 'uninitialized', version: 'uninitialized' };

// Add handler for initialization method - capture client info
server.setRequestHandler(InitializeRequestSchema, async (request: InitializeRequest) => {
    try {
        // Extract and store current client information
        const clientInfo = request.params?.clientInfo;
        if (clientInfo) {
            currentClient = {
                name: clientInfo.name || 'unknown',
                version: clientInfo.version || 'unknown'
            };
            // Defer client connection message until after initialization
            deferLog('info', `Client connected: ${currentClient.name} v${currentClient.version}`);
        }

        // Return standard initialization response
        return {
            protocolVersion: "2024-11-05",
            capabilities: {
                tools: {},
                resources: {},
                prompts: {},
                logging: {},
            },
            serverInfo: {
                name: "desktop-commander",
                version: VERSION,
            },
        };
    } catch (error) {
        logToStderr('error', `Error in initialization handler: ${error}`);
        throw error;
    }
});

// Export current client info for access by other modules
export { currentClient };

deferLog('info', 'Setting up request handlers...');

server.setRequestHandler(ListToolsRequestSchema, async () => {
    try {
        logToStderr('debug', 'Generating tools list...');
        return {
            tools: [
                // Filesystem tools
                {
                    name: "read_file",
                    description: `
                        Read contents of a text file with optional line range.

                        Parameters:
                        - 'offset': Starting line (default: 0, 0-indexed)
                        * Positive N: Start from line N
                        * Negative N: Start N lines from end (e.g., -20 = last 20 lines)
                        - 'length': Max lines to read (default: all remaining lines)

                        Examples:
                        - (no params)             → Read entire file
                        - offset: 0, length: 10   → Lines 0-9 (first 10 lines)
                        - offset: 100, length: 5  → Lines 100-104
                        - offset: -20             → Last 20 lines
                    `,
                    inputSchema: zodToJsonSchema(ReadFileArgsSchema),
                    annotations: {
                        title: "Read Text File",
                        readOnlyHint: true,
                        openWorldHint: true,
                    },
                },
                {
                    name: "write_file",
                    description: `
                        Write or append to file contents`,
                    inputSchema: zodToJsonSchema(WriteFileArgsSchema),
                    annotations: {
                        title: "Write Text File",
                        readOnlyHint: false,
                        destructiveHint: true,
                        openWorldHint: false,
                    },
                },
                {
                    name: "move_file",
                    description: `
                        Move or rename files and directories.
                        Can move files between directories and rename them in a single operation`,
                    inputSchema: zodToJsonSchema(MoveFileArgsSchema),
                    annotations: {
                        title: "Move/Rename File",
                        readOnlyHint: false,
                        destructiveHint: true,
                        openWorldHint: false,
                    },
                },
                {
                    name: "edit_file",
                    description: `
                        Apply surgical text replacements to files.

                        Parameters:
                        - file_path: Path to the file to edit
                        - old_string: Text to replace
                        - new_string: Replacement text
                        - expected_replacements: Optional parameter for number of replacements

                        By default, replaces only ONE occurrence of the search text.
                        To replace multiple occurrences, provide the expected_replacements parameter with
                        the exact number of matches expected.

                        When a close but non-exact match is found, a character-level diff is shown in the format:
                        common_prefix{-removed-}{+added+}common_suffix to help you identify what's different`,
                    inputSchema: zodToJsonSchema(EditBlockArgsSchema),
                    annotations: {
                        title: "Edit Text File",
                        readOnlyHint: false,
                        destructiveHint: true,
                        openWorldHint: false,
                    },
                },

                // directory management tools
                {
                    name: "create_directory",
                    description: `
                        Create a new directory or ensure a directory exists.
                        Can create multiple nested directories in one operation`,
                    inputSchema: zodToJsonSchema(CreateDirectoryArgsSchema),
                },
                {
                    name: "list_directory",
                    description: `
                        Get a detailed listing of all files and directories in a specified path.
                        Results distinguish between files and directories with [FILE] and [DIR] prefixes`,
                    inputSchema: zodToJsonSchema(ListDirectoryArgsSchema),
                    annotations: {
                        title: "List Directory Contents",
                        readOnlyHint: true,
                    },
                },


                // Terminal tools
                {
                    name: "execute_command",
                    description: `
                        Execute a terminal command`,
                    inputSchema: {
                        type: "object",
                        properties: {
                            command: {
                                type: "string",
                                description: "The command to execute"
                            },
                        },
                        required: ["command"]
                    },
                    annotations: {
                        title: "Execute Terminal Command",
                        readOnlyHint: false,
                        destructiveHint: true,
                        openWorldHint: true,
                    },
                },
            ],
        };
    } catch (error) {
        logToStderr('error', `Error in list_tools request handler: ${error}`);
        throw error;
    }
});

import * as handlers from './handlers/index.js';
import { ServerResult } from './types.js';

server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest): Promise<ServerResult> => {
    const { name, arguments: args } = request.params;

    try {
        // Prepare telemetry data - add config key for set_config_value
        const telemetryData: any = { name };
        if (name === 'set_config_value' && args && typeof args === 'object' && 'key' in args) {
            telemetryData.set_config_value_key_name = (args as any).key;
        }
        if (name === 'get_prompts' && args && typeof args === 'object') {
            const promptArgs = args as any;
            telemetryData.action = promptArgs.action;
            if (promptArgs.category) {
                telemetryData.category = promptArgs.category;
                telemetryData.has_category_filter = true;
            }
            if (promptArgs.promptId) {
                telemetryData.prompt_id = promptArgs.promptId;
            }
        }

        capture_call_tool('server_call_tool', telemetryData);

        // Track tool call
        trackToolCall(name, args);

        // Using a more structured approach with dedicated handlers
        let result: ServerResult;

        switch (name) {
            // Config tools
            case "get_config":
                try {
                    result = await getConfig();
                } catch (error) {
                    capture('server_request_error', { message: `Error in get_config handler: ${error}` });
                    result = {
                        content: [{ type: "text", text: `Error: Failed to get configuration` }],
                        isError: true,
                    };
                }
                break;
            case "set_config_value":
                try {
                    result = await setConfigValue(args);
                } catch (error) {
                    capture('server_request_error', { message: `Error in set_config_value handler: ${error}` });
                    result = {
                        content: [{ type: "text", text: `Error: Failed to set configuration value` }],
                        isError: true,
                    };
                }
                break;

            case "get_usage_stats":
                try {
                    result = await getUsageStats();
                } catch (error) {
                    capture('server_request_error', { message: `Error in get_usage_stats handler: ${error}` });
                    result = {
                        content: [{ type: "text", text: `Error: Failed to get usage statistics` }],
                        isError: true,
                    };
                }
                break;

            case "get_prompts":
                try {
                    result = await getPrompts(args || {});

                    // Capture detailed analytics for all successful get_prompts actions
                    if (args && typeof args === 'object' && !result.isError) {
                        const action = (args as any).action;

                        try {
                            if (action === 'get_prompt' && (args as any).promptId) {
                                // Existing get_prompt analytics
                                const { loadPromptsData } = await import('./tools/prompts.js');
                                const promptsData = await loadPromptsData();
                                const prompt = promptsData.prompts.find(p => p.id === (args as any).promptId);
                                if (prompt) {
                                    await capture('server_get_prompt', {
                                        prompt_id: prompt.id,
                                        prompt_title: prompt.title,
                                        category: prompt.categories[0] || 'uncategorized',
                                        author: prompt.author,
                                        verified: prompt.verified
                                    });
                                }
                            } else if (action === 'list_categories') {
                                // New analytics for category browsing
                                const { loadPromptsData } = await import('./tools/prompts.js');
                                const promptsData = await loadPromptsData();

                                // Extract unique categories and count prompts in each
                                const categoryMap = new Map<string, number>();
                                promptsData.prompts.forEach(prompt => {
                                    prompt.categories.forEach(category => {
                                        categoryMap.set(category, (categoryMap.get(category) || 0) + 1);
                                    });
                                });

                                await capture('server_list_prompt_categories', {
                                    total_categories: categoryMap.size,
                                    total_prompts: promptsData.prompts.length,
                                    categories_available: Array.from(categoryMap.keys())
                                });
                            } else if (action === 'list_prompts') {
                                // New analytics for prompt list browsing
                                const { loadPromptsData } = await import('./tools/prompts.js');
                                const promptsData = await loadPromptsData();

                                const category = (args as any).category;
                                let filteredPrompts = promptsData.prompts;

                                if (category) {
                                    filteredPrompts = promptsData.prompts.filter(prompt =>
                                        prompt.categories.includes(category)
                                    );
                                }

                                await capture('server_list_category_prompts', {
                                    category_filter: category || 'all',
                                    has_category_filter: !!category,
                                    prompts_shown: filteredPrompts.length,
                                    total_prompts_available: promptsData.prompts.length,
                                    prompt_ids_shown: filteredPrompts.map(p => p.id)
                                });
                            }
                        } catch (error) {
                            // Don't fail the request if analytics fail
                        }
                    }

                    // Track if user used get_prompts after seeing onboarding invitation (for state management only)
                    const onboardingState = await usageTracker.getOnboardingState();
                    if (onboardingState.attemptsShown > 0 && !onboardingState.promptsUsed) {
                        // Mark that they used prompts after seeing onboarding (stops future onboarding messages)
                        await usageTracker.markOnboardingPromptsUsed();
                    }
                } catch (error) {
                    capture('server_request_error', { message: `Error in get_prompts handler: ${error}` });
                    result = {
                        content: [{ type: "text", text: `Error: Failed to retrieve prompts` }],
                        isError: true,
                    };
                }
                break;

            case "give_feedback_to_desktop_commander":
                try {
                    result = await giveFeedbackToDesktopCommander(args);
                } catch (error) {
                    capture('server_request_error', { message: `Error in give_feedback_to_desktop_commander handler: ${error}` });
                    result = {
                        content: [{ type: "text", text: `Error: Failed to open feedback form` }],
                        isError: true,
                    };
                }
                break;

            // Terminal tools
            case "execute_command":
                result = await handlers.handleStartProcess({
                    ...args,
                    timeout_ms: 60000  // ? Fixed 60 second timeout
                });
                break;

            case "read_process_output":
                result = await handlers.handleReadProcessOutput(args);
                break;

            case "interact_with_process":
                result = await handlers.handleInteractWithProcess(args);
                break;

            case "force_terminate":
                result = await handlers.handleForceTerminate(args);
                break;

            case "list_sessions":
                result = await handlers.handleListSessions();
                break;

            // Process tools
            case "list_processes":
                result = await handlers.handleListProcesses();
                break;

            case "kill_process":
                result = await handlers.handleKillProcess(args);
                break;

            // Note: REPL functionality removed in favor of using general terminal commands

            // Filesystem tools
            case "read_file":
                result = await handlers.handleReadFile(args);
                break;

            case "read_multiple_files":
                result = await handlers.handleReadMultipleFiles(args);
                break;

            case "write_file":
                result = await handlers.handleWriteFile(args);
                break;

            case "create_directory":
                result = await handlers.handleCreateDirectory(args);
                break;

            case "list_directory":
                result = await handlers.handleListDirectory(args);
                break;

            case "move_file":
                result = await handlers.handleMoveFile(args);
                break;

            case "start_search":
                result = await handlers.handleStartSearch(args);
                break;

            case "get_more_search_results":
                result = await handlers.handleGetMoreSearchResults(args);
                break;

            case "stop_search":
                result = await handlers.handleStopSearch(args);
                break;

            case "list_searches":
                result = await handlers.handleListSearches();
                break;

            case "get_file_info":
                result = await handlers.handleGetFileInfo(args);
                break;

            case "edit_file":
                result = await handlers.handleEditBlock(args);
                break;

            default:
                capture('server_unknown_tool', { name });
                result = {
                    content: [{ type: "text", text: `Error: Unknown tool: ${name}` }],
                    isError: true,
                };
        }

        // Track success or failure based on result
        if (result.isError) {
            await usageTracker.trackFailure(name);
            console.log(`[FEEDBACK DEBUG] Tool ${name} failed, not checking feedback`);
        } else {
            await usageTracker.trackSuccess(name);
            console.log(`[FEEDBACK DEBUG] Tool ${name} succeeded, checking feedback...`);

            // Check if should show onboarding (before feedback - first-time users are priority)
            const shouldShowOnboarding = await usageTracker.shouldShowOnboarding();
            console.log(`[ONBOARDING DEBUG] Should show onboarding: ${shouldShowOnboarding}`);

            if (shouldShowOnboarding) {
                console.log(`[ONBOARDING DEBUG] Generating onboarding message...`);
                const onboardingResult = await usageTracker.getOnboardingMessage();
                console.log(`[ONBOARDING DEBUG] Generated variant: ${onboardingResult.variant}`);

                // Capture onboarding prompt injection event
                const stats = await usageTracker.getStats();
                await capture('server_onboarding_shown', {
                    trigger_tool: name,
                    total_calls: stats.totalToolCalls,
                    successful_calls: stats.successfulCalls,
                    days_since_first_use: Math.floor((Date.now() - stats.firstUsed) / (1000 * 60 * 60 * 24)),
                    total_sessions: stats.totalSessions,
                    message_variant: onboardingResult.variant
                });

                // Inject onboarding message for the LLM
                if (result.content && result.content.length > 0 && result.content[0].type === "text") {
                    const currentContent = result.content[0].text || '';
                    result.content[0].text = `${currentContent}${onboardingResult.message}`;
                } else {
                    result.content = [
                        ...(result.content || []),
                        {
                            type: "text",
                            text: onboardingResult.message
                        }
                    ];
                }

                // Mark that we've shown onboarding (to prevent spam)
                await usageTracker.markOnboardingShown(onboardingResult.variant);
            }

            // Check if should prompt for feedback (only on successful operations)
            const shouldPrompt = await usageTracker.shouldPromptForFeedback();
            console.log(`[FEEDBACK DEBUG] Should prompt for feedback: ${shouldPrompt}`);

            if (shouldPrompt) {
                console.log(`[FEEDBACK DEBUG] Generating feedback message...`);
                const feedbackResult = await usageTracker.getFeedbackPromptMessage();
                console.log(`[FEEDBACK DEBUG] Generated variant: ${feedbackResult.variant}`);

                // Capture feedback prompt injection event
                const stats = await usageTracker.getStats();
                await capture('feedback_prompt_injected', {
                    trigger_tool: name,
                    total_calls: stats.totalToolCalls,
                    successful_calls: stats.successfulCalls,
                    failed_calls: stats.failedCalls,
                    days_since_first_use: Math.floor((Date.now() - stats.firstUsed) / (1000 * 60 * 60 * 24)),
                    total_sessions: stats.totalSessions,
                    message_variant: feedbackResult.variant
                });

                // Inject feedback instruction for the LLM
                if (result.content && result.content.length > 0 && result.content[0].type === "text") {
                    const currentContent = result.content[0].text || '';
                    result.content[0].text = `${currentContent}${feedbackResult.message}`;
                } else {
                    result.content = [
                        ...(result.content || []),
                        {
                            type: "text",
                            text: feedbackResult.message
                        }
                    ];
                }

                // Mark that we've prompted (to prevent spam)
                await usageTracker.markFeedbackPrompted();
            }

            // Check if should prompt about Docker environment
            result = await processDockerPrompt(result, name);
        }

        return result;
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);

        // Track the failure
        await usageTracker.trackFailure(name);

        capture('server_request_error', {
            error: errorMessage
        });
        return {
            content: [{ type: "text", text: `Error: ${errorMessage}` }],
            isError: true,
        };
    }
});

// Add no-op handlers so Visual Studio initialization succeeds
server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({ resourceTemplates: [] }));