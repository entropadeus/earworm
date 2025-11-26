"""
Text processing module for Earworm.
Handles voice commands, smart punctuation, and text transformations.

This module provides a pipeline architecture for processing transcribed text:
1. Voice command detection and execution
2. Smart punctuation restoration
3. Text normalization and formatting
"""

import re
from typing import Optional, Callable, List, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod


class CommandAction(Enum):
    """Actions that voice commands can trigger."""
    INSERT_TEXT = auto()      # Insert specific text
    DELETE_LAST = auto()      # Delete last chunk/word
    DELETE_ALL = auto()       # Clear everything
    NEW_LINE = auto()         # Insert line break
    NEW_PARAGRAPH = auto()    # Insert paragraph break
    CAPITALIZE_NEXT = auto()  # Capitalize next word
    UPPERCASE_NEXT = auto()   # Uppercase next word
    LOWERCASE_NEXT = auto()   # Lowercase next word
    NO_SPACE_NEXT = auto()    # No space before next insertion
    UNDO = auto()             # Undo last action
    SELECT_ALL = auto()       # Select all text
    NAVIGATION = auto()       # Navigation command


@dataclass
class CommandResult:
    """Result of processing a voice command."""
    action: CommandAction
    text: str = ""           # Text to insert (for INSERT_TEXT)
    remove_trigger: bool = True  # Whether to remove the trigger phrase
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingContext:
    """Context maintained during text processing."""
    capitalize_next: bool = False
    uppercase_next: bool = False
    lowercase_next: bool = False
    no_space_next: bool = False
    history: List[str] = field(default_factory=list)

    def reset_word_modifiers(self) -> None:
        """Reset one-time word modifiers after use."""
        self.capitalize_next = False
        self.uppercase_next = False
        self.lowercase_next = False
        self.no_space_next = False


class VoiceCommand:
    """Represents a single voice command with its triggers and action."""

    def __init__(
        self,
        triggers: List[str],
        action: CommandAction,
        text: str = "",
        case_sensitive: bool = False,
        word_boundary: bool = True,
        priority: int = 0
    ):
        """
        Args:
            triggers: List of phrases that trigger this command
            action: The action to perform
            text: Text to insert (for INSERT_TEXT action)
            case_sensitive: Whether matching is case-sensitive
            word_boundary: Whether to match only at word boundaries
            priority: Higher priority commands are checked first
        """
        self.triggers = triggers
        self.action = action
        self.text = text
        self.case_sensitive = case_sensitive
        self.word_boundary = word_boundary
        self.priority = priority

        # Pre-compile regex patterns for efficiency
        self._patterns = []
        for trigger in triggers:
            flags = 0 if case_sensitive else re.IGNORECASE
            if word_boundary:
                # Match at word boundaries, handling start/end of string
                pattern = rf'(?:^|\s)({re.escape(trigger)})(?:\s|$|[.,!?;:])'
            else:
                pattern = rf'({re.escape(trigger)})'
            self._patterns.append(re.compile(pattern, flags))

    def find_in_text(self, text: str) -> Optional[Tuple[int, int, str]]:
        """
        Find this command's trigger in text.

        Returns:
            Tuple of (start_index, end_index, matched_text) or None
        """
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                # Get the actual trigger group
                group_start = match.start(1)
                group_end = match.end(1)
                return (group_start, group_end, match.group(1))
        return None

    def execute(self) -> CommandResult:
        """Execute this command and return the result."""
        return CommandResult(
            action=self.action,
            text=self.text,
            remove_trigger=True
        )


class VoiceCommandProcessor:
    """
    Processes voice commands in transcribed text.

    Supports commands like:
    - Punctuation: "period", "comma", "question mark", etc.
    - Formatting: "new line", "new paragraph"
    - Editing: "delete that", "undo", "scratch that"
    - Capitalization: "capitalize", "all caps", "lowercase"
    """

    # Default commands - easily extensible
    DEFAULT_COMMANDS = [
        # Punctuation - High priority
        VoiceCommand(["period", "full stop"], CommandAction.INSERT_TEXT, ".", priority=10),
        VoiceCommand(["comma"], CommandAction.INSERT_TEXT, ",", priority=10),
        VoiceCommand(["question mark"], CommandAction.INSERT_TEXT, "?", priority=10),
        VoiceCommand(["exclamation mark", "exclamation point"], CommandAction.INSERT_TEXT, "!", priority=10),
        VoiceCommand(["colon"], CommandAction.INSERT_TEXT, ":", priority=10),
        VoiceCommand(["semicolon", "semi colon"], CommandAction.INSERT_TEXT, ";", priority=10),
        VoiceCommand(["hyphen", "dash"], CommandAction.INSERT_TEXT, "-", priority=10),
        VoiceCommand(["underscore"], CommandAction.INSERT_TEXT, "_", priority=10),
        VoiceCommand(["ellipsis", "dot dot dot"], CommandAction.INSERT_TEXT, "...", priority=10),
        VoiceCommand(["ampersand", "and sign"], CommandAction.INSERT_TEXT, "&", priority=10),
        VoiceCommand(["at sign", "at symbol"], CommandAction.INSERT_TEXT, "@", priority=10),
        VoiceCommand(["hashtag", "hash", "pound sign"], CommandAction.INSERT_TEXT, "#", priority=10),
        VoiceCommand(["dollar sign"], CommandAction.INSERT_TEXT, "$", priority=10),
        VoiceCommand(["percent sign", "percent"], CommandAction.INSERT_TEXT, "%", priority=10),
        VoiceCommand(["asterisk", "star"], CommandAction.INSERT_TEXT, "*", priority=10),
        VoiceCommand(["plus sign"], CommandAction.INSERT_TEXT, "+", priority=10),
        VoiceCommand(["equals sign", "equal sign"], CommandAction.INSERT_TEXT, "=", priority=10),
        VoiceCommand(["forward slash", "slash"], CommandAction.INSERT_TEXT, "/", priority=10),
        VoiceCommand(["backslash", "back slash"], CommandAction.INSERT_TEXT, "\\", priority=10),
        VoiceCommand(["vertical bar", "pipe"], CommandAction.INSERT_TEXT, "|", priority=10),

        # Quotes and brackets
        VoiceCommand(["open quote", "begin quote", "quote"], CommandAction.INSERT_TEXT, '"', priority=10),
        VoiceCommand(["close quote", "end quote", "unquote"], CommandAction.INSERT_TEXT, '"', priority=10),
        VoiceCommand(["single quote", "apostrophe"], CommandAction.INSERT_TEXT, "'", priority=10),
        VoiceCommand(["open paren", "open parenthesis", "left paren"], CommandAction.INSERT_TEXT, "(", priority=10),
        VoiceCommand(["close paren", "close parenthesis", "right paren"], CommandAction.INSERT_TEXT, ")", priority=10),
        VoiceCommand(["open bracket", "left bracket"], CommandAction.INSERT_TEXT, "[", priority=10),
        VoiceCommand(["close bracket", "right bracket"], CommandAction.INSERT_TEXT, "]", priority=10),
        VoiceCommand(["open brace", "left brace"], CommandAction.INSERT_TEXT, "{", priority=10),
        VoiceCommand(["close brace", "right brace"], CommandAction.INSERT_TEXT, "}", priority=10),
        VoiceCommand(["less than", "left angle"], CommandAction.INSERT_TEXT, "<", priority=10),
        VoiceCommand(["greater than", "right angle"], CommandAction.INSERT_TEXT, ">", priority=10),

        # Line/paragraph control - Medium-high priority
        VoiceCommand(["new line", "newline", "line break"], CommandAction.NEW_LINE, priority=8),
        VoiceCommand(["new paragraph", "paragraph break"], CommandAction.NEW_PARAGRAPH, priority=8),
        VoiceCommand(["tab", "tab key"], CommandAction.INSERT_TEXT, "\t", priority=8),

        # Editing commands - Medium priority
        VoiceCommand(["delete that", "scratch that", "erase that"], CommandAction.DELETE_LAST, priority=5),
        VoiceCommand(["delete all", "clear all", "erase all", "start over"], CommandAction.DELETE_ALL, priority=5),
        VoiceCommand(["undo", "undo that"], CommandAction.UNDO, priority=5),
        VoiceCommand(["select all"], CommandAction.SELECT_ALL, priority=5),

        # Capitalization commands - Medium priority
        VoiceCommand(["capitalize", "cap"], CommandAction.CAPITALIZE_NEXT, priority=5),
        VoiceCommand(["all caps", "uppercase", "all uppercase"], CommandAction.UPPERCASE_NEXT, priority=5),
        VoiceCommand(["lowercase", "all lowercase", "no caps"], CommandAction.LOWERCASE_NEXT, priority=5),

        # Spacing control
        VoiceCommand(["no space", "nospace"], CommandAction.NO_SPACE_NEXT, priority=5),

        # Common words that might be misheard as commands - handle specially
        VoiceCommand(["literal period"], CommandAction.INSERT_TEXT, "period", priority=15),
        VoiceCommand(["literal comma"], CommandAction.INSERT_TEXT, "comma", priority=15),
        VoiceCommand(["literal colon"], CommandAction.INSERT_TEXT, "colon", priority=15),
    ]

    def __init__(self, custom_commands: Optional[List[VoiceCommand]] = None):
        """
        Args:
            custom_commands: Additional commands to register
        """
        self._commands = list(self.DEFAULT_COMMANDS)
        if custom_commands:
            self._commands.extend(custom_commands)

        # Sort by priority (highest first)
        self._commands.sort(key=lambda c: -c.priority)

        self._context = ProcessingContext()
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def add_command(self, command: VoiceCommand) -> None:
        """Add a custom command."""
        self._commands.append(command)
        self._commands.sort(key=lambda c: -c.priority)

    def process(self, text: str) -> Tuple[str, List[CommandResult]]:
        """
        Process text and execute any voice commands found.

        Args:
            text: Raw transcribed text

        Returns:
            Tuple of (processed_text, list_of_executed_commands)
        """
        if not self._enabled or not text:
            return text, []

        executed_commands = []
        result_parts = []
        remaining = text

        while remaining:
            # Find the earliest command in the remaining text
            earliest_match = None
            earliest_command = None
            earliest_pos = len(remaining)

            for command in self._commands:
                match = command.find_in_text(remaining)
                if match and match[0] < earliest_pos:
                    earliest_pos = match[0]
                    earliest_match = match
                    earliest_command = command

            if earliest_match and earliest_command:
                start, end, matched = earliest_match

                # Add text before the command
                if start > 0:
                    before_text = remaining[:start].strip()
                    if before_text:
                        result_parts.append(self._apply_modifiers(before_text))

                # Execute the command
                cmd_result = earliest_command.execute()
                executed_commands.append(cmd_result)

                # Handle the command result
                self._handle_command_result(cmd_result, result_parts)

                # Move past the command
                remaining = remaining[end:].lstrip()
            else:
                # No more commands, add remaining text
                if remaining.strip():
                    result_parts.append(self._apply_modifiers(remaining.strip()))
                break

        # Join parts intelligently
        processed = self._join_parts(result_parts)

        # Save to history for undo
        self._context.history.append(processed)

        return processed, executed_commands

    def _apply_modifiers(self, text: str) -> str:
        """Apply any pending word modifiers to text."""
        if not text:
            return text

        if self._context.uppercase_next:
            text = text.upper()
            self._context.uppercase_next = False
        elif self._context.lowercase_next:
            text = text.lower()
            self._context.lowercase_next = False
        elif self._context.capitalize_next:
            text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
            self._context.capitalize_next = False

        return text

    def _handle_command_result(self, result: CommandResult, parts: List[str]) -> None:
        """Handle a command result, updating parts and context."""
        if result.action == CommandAction.INSERT_TEXT:
            parts.append(result.text)
        elif result.action == CommandAction.NEW_LINE:
            parts.append("\n")
        elif result.action == CommandAction.NEW_PARAGRAPH:
            parts.append("\n\n")
        elif result.action == CommandAction.DELETE_LAST:
            if parts:
                parts.pop()
        elif result.action == CommandAction.DELETE_ALL:
            parts.clear()
        elif result.action == CommandAction.CAPITALIZE_NEXT:
            self._context.capitalize_next = True
        elif result.action == CommandAction.UPPERCASE_NEXT:
            self._context.uppercase_next = True
        elif result.action == CommandAction.LOWERCASE_NEXT:
            self._context.lowercase_next = True
        elif result.action == CommandAction.NO_SPACE_NEXT:
            self._context.no_space_next = True
        elif result.action == CommandAction.UNDO:
            if len(self._context.history) > 1:
                self._context.history.pop()  # Remove current
                parts.clear()
                parts.append(self._context.history[-1])

    def _join_parts(self, parts: List[str]) -> str:
        """Join text parts with appropriate spacing."""
        if not parts:
            return ""

        result = []
        no_space_chars = set('.,!?;:)]\'"}-')  # Don't add space before these
        no_space_after = set('([{\'"$#@')       # Don't add space after these

        for i, part in enumerate(parts):
            if not part:
                continue

            if i == 0:
                result.append(part)
            else:
                # Check if we need space before this part
                needs_space = True

                if part[0] in no_space_chars:
                    needs_space = False
                elif part == "\n" or part == "\n\n":
                    needs_space = False
                elif result and result[-1] and result[-1][-1] in no_space_after:
                    needs_space = False
                elif result and result[-1] and result[-1][-1] in '\n':
                    needs_space = False
                elif self._context.no_space_next:
                    needs_space = False
                    self._context.no_space_next = False

                if needs_space:
                    result.append(" ")
                result.append(part)

        return "".join(result)

    def reset(self) -> None:
        """Reset processing context."""
        self._context = ProcessingContext()


class SmartPunctuator:
    """
    Adds smart punctuation to transcribed text.

    Uses a combination of:
    1. Rule-based patterns (fast, predictable)
    2. Statistical/ML approaches (optional, more accurate)

    This is designed to be modular - you can use just rules,
    or add ML-based punctuation for better results.
    """

    # Sentence-ending patterns (questions, etc.)
    QUESTION_STARTERS = {
        'who', 'what', 'when', 'where', 'why', 'how',
        'is', 'are', 'was', 'were', 'will', 'would', 'could', 'should',
        'can', 'do', 'does', 'did', 'have', 'has', 'had',
        "isn't", "aren't", "wasn't", "weren't", "won't", "wouldn't",
        "couldn't", "shouldn't", "can't", "don't", "doesn't", "didn't"
    }

    # Words that typically start sentences
    SENTENCE_STARTERS = {
        'i', 'the', 'a', 'an', 'this', 'that', 'these', 'those',
        'my', 'your', 'his', 'her', 'its', 'our', 'their',
        'we', 'they', 'he', 'she', 'it', 'you',
        'there', 'here', 'now', 'then', 'so', 'but', 'and', 'or',
        'if', 'when', 'while', 'although', 'because', 'since',
        'however', 'therefore', 'furthermore', 'moreover',
        'first', 'second', 'third', 'finally', 'next', 'last',
        'please', 'let', 'just', 'also', 'well', 'actually'
    }

    # Common abbreviations that shouldn't end sentences
    ABBREVIATIONS = {
        'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr',
        'vs', 'etc', 'inc', 'ltd', 'co', 'corp',
        'st', 'ave', 'blvd', 'rd', 'apt',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    }

    # Pause words that often indicate clause boundaries
    PAUSE_INDICATORS = {
        'um', 'uh', 'er', 'ah', 'like', 'you know', 'i mean',
        'well', 'so', 'anyway', 'basically', 'actually', 'honestly'
    }

    def __init__(
        self,
        auto_capitalize: bool = True,
        auto_periods: bool = True,
        auto_commas: bool = True,
        auto_questions: bool = True,
        remove_fillers: bool = False,  # Remove "um", "uh", etc.
        ml_punctuator: Optional[Any] = None  # Future: ML model for punctuation
    ):
        self.auto_capitalize = auto_capitalize
        self.auto_periods = auto_periods
        self.auto_commas = auto_commas
        self.auto_questions = auto_questions
        self.remove_fillers = remove_fillers
        self._ml_punctuator = ml_punctuator
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def process(self, text: str) -> str:
        """
        Add smart punctuation to text.

        Args:
            text: Text to punctuate (may already have some punctuation)

        Returns:
            Text with improved punctuation
        """
        if not self._enabled or not text or not text.strip():
            return text

        # If ML punctuator is available, use it
        if self._ml_punctuator:
            return self._ml_punctuate(text)

        # Otherwise, use rule-based approach
        return self._rule_based_punctuate(text)

    def _rule_based_punctuate(self, text: str) -> str:
        """Apply rule-based punctuation."""
        # Step 1: Clean up and normalize
        text = self._normalize_whitespace(text)

        # Step 2: Remove filler words if configured
        if self.remove_fillers:
            text = self._remove_fillers(text)

        # Step 3: Detect sentence boundaries and add periods
        if self.auto_periods:
            text = self._add_sentence_punctuation(text)

        # Step 4: Add commas at natural pause points
        if self.auto_commas:
            text = self._add_commas(text)

        # Step 5: Capitalize sentence starts
        if self.auto_capitalize:
            text = self._capitalize_sentences(text)

        # Step 6: Fix common issues
        text = self._fix_punctuation_spacing(text)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Collapse multiple spaces
        text = re.sub(r' +', ' ', text)
        # Normalize newlines
        text = re.sub(r'\n+', '\n', text)
        return text.strip()

    def _remove_fillers(self, text: str) -> str:
        """Remove filler words like 'um', 'uh'."""
        words = text.split()
        filtered = []

        for word in words:
            word_lower = word.lower().strip('.,!?;:')
            if word_lower not in {'um', 'uh', 'er', 'ah', 'hmm', 'mm'}:
                filtered.append(word)

        return ' '.join(filtered)

    def _add_sentence_punctuation(self, text: str) -> str:
        """
        Add periods and question marks at sentence boundaries.

        Uses heuristics:
        - Long pauses (represented by existing punctuation or structure)
        - Question word patterns
        - Natural sentence length limits

        Preserves explicit newlines in the text.
        """
        # Process line by line to preserve newlines
        lines = text.split('\n')
        processed_lines = []

        for line in lines:
            if not line.strip():
                processed_lines.append(line)
                continue

            words = line.split()
            if not words:
                processed_lines.append(line)
                continue

            result = []
            current_sentence = []
            is_question = False

            for i, word in enumerate(words):
                word_lower = word.lower()

                # Check if this word starts a question
                if not current_sentence and word_lower in self.QUESTION_STARTERS:
                    is_question = True

                current_sentence.append(word)

                # Check for existing sentence-ending punctuation
                if word.rstrip()[-1:] in '.!?':
                    result.extend(current_sentence)
                    current_sentence = []
                    is_question = False
                    continue

                # Heuristic: End sentence if:
                # 1. We hit a natural boundary word pattern
                # 2. Sentence is getting long (>15 words without punctuation)
                # 3. Next word is a strong sentence starter

                should_end = False

                # Check if next word is a strong sentence starter
                if i + 1 < len(words):
                    next_word = words[i + 1].lower()
                    # Strong starters after some content
                    if (len(current_sentence) >= 4 and
                        next_word in {'i', 'we', 'they', 'he', 'she', 'it', 'the', 'so', 'but', 'however', 'therefore'}):
                        should_end = True

                # Long sentence heuristic
                if len(current_sentence) >= 20:
                    should_end = True

                if should_end:
                    # Add appropriate punctuation
                    last_word = current_sentence[-1]
                    punct = '?' if is_question else '.'

                    # Don't double-punctuate
                    if last_word[-1] not in '.!?,;:':
                        current_sentence[-1] = last_word + punct

                    result.extend(current_sentence)
                    current_sentence = []
                    is_question = False

            # Add remaining words
            if current_sentence:
                # Add period at end if no punctuation
                last_word = current_sentence[-1]
                if last_word[-1:] not in '.!?,;:':
                    punct = '?' if is_question else '.'
                    current_sentence[-1] = last_word + punct
                result.extend(current_sentence)

            processed_lines.append(' '.join(result))

        return '\n'.join(processed_lines)

    def _add_commas(self, text: str) -> str:
        """
        Add commas at natural pause points.

        Rules:
        - After introductory phrases
        - Before coordinating conjunctions in compound sentences
        - Around parenthetical elements
        """
        # Introductory phrases that typically need commas
        intro_patterns = [
            r'^(Well)(\s)',
            r'^(So)(\s)',
            r'^(Now)(\s)',
            r'^(Actually)(\s)',
            r'^(However)(\s)',
            r'^(Therefore)(\s)',
            r'^(First|Second|Third|Finally)(\s)',
            r'^(In fact)(\s)',
            r'^(Of course)(\s)',
            r'^(For example)(\s)',
            r'^(On the other hand)(\s)',
        ]

        sentences = re.split(r'([.!?]+)', text)
        result = []

        for i, part in enumerate(sentences):
            if not part or part in '.!?':
                result.append(part)
                continue

            # Apply intro patterns
            for pattern in intro_patterns:
                if re.match(pattern, part, re.IGNORECASE):
                    # Check if comma already exists
                    match = re.match(pattern, part, re.IGNORECASE)
                    if match:
                        intro = match.group(1)
                        # Only add comma if not already present
                        if not part[len(intro):len(intro)+1] == ',':
                            part = intro + ',' + part[match.end(1):]
                    break

            # Add commas before coordinating conjunctions in longer sentences
            # Pattern: [content] and/but/or [content] where each part is substantial
            conj_pattern = r'(\w{15,})\s+(and|but|or)\s+(\w)'
            part = re.sub(
                conj_pattern,
                lambda m: m.group(1) + ', ' + m.group(2) + ' ' + m.group(3),
                part,
                flags=re.IGNORECASE
            )

            result.append(part)

        return ''.join(result)

    def _capitalize_sentences(self, text: str) -> str:
        """Capitalize the first letter of each sentence."""
        if not text:
            return text

        # Capitalize first character
        result = text[0].upper() + text[1:] if text else text

        # Capitalize after sentence-ending punctuation (preserve the whitespace type)
        # Match punctuation followed by space(s) and lowercase letter
        result = re.sub(
            r'([.!?])( +)([a-z])',
            lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
            result
        )

        # Capitalize after newlines (handles both \n and \n with spaces)
        result = re.sub(
            r'(\n\s*)([a-z])',
            lambda m: m.group(1) + m.group(2).upper(),
            result
        )

        # Capitalize after punctuation followed by newline
        result = re.sub(
            r'([.!?])(\n\s*)([a-z])',
            lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
            result
        )

        # Always capitalize "I"
        result = re.sub(r'\bi\b', 'I', result)

        return result

    def _fix_punctuation_spacing(self, text: str) -> str:
        """Fix common punctuation spacing issues."""
        # Remove space before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)

        # Ensure space after punctuation (except at end or before newline)
        text = re.sub(r'([.,!?;:])([A-Za-z])', r'\1 \2', text)

        # Fix multiple punctuation
        text = re.sub(r'([.!?]){2,}', r'\1', text)

        # Fix comma followed by period
        text = re.sub(r',\.', '.', text)

        return text

    def _ml_punctuate(self, text: str) -> str:
        """
        Use ML model for punctuation (future extension point).

        This could integrate with:
        - deepmultilingualpunctuation
        - rpunct
        - Custom fine-tuned model
        """
        if self._ml_punctuator:
            try:
                return self._ml_punctuator(text)
            except Exception as e:
                print(f"ML punctuation failed, falling back to rules: {e}")

        return self._rule_based_punctuate(text)


class TextProcessingPipeline:
    """
    Main text processing pipeline that orchestrates all transformations.

    Pipeline stages:
    1. Voice command processing
    2. Smart punctuation
    3. Custom post-processors (extensible)
    """

    def __init__(
        self,
        enable_voice_commands: bool = True,
        enable_smart_punctuation: bool = True,
        voice_command_processor: Optional[VoiceCommandProcessor] = None,
        smart_punctuator: Optional[SmartPunctuator] = None
    ):
        self._voice_commands = voice_command_processor or VoiceCommandProcessor()
        self._punctuator = smart_punctuator or SmartPunctuator()

        self._voice_commands.enabled = enable_voice_commands
        self._punctuator.enabled = enable_smart_punctuation

        # Custom post-processors (extensible)
        self._post_processors: List[Callable[[str], str]] = []

    @property
    def voice_commands(self) -> VoiceCommandProcessor:
        """Access voice command processor for configuration."""
        return self._voice_commands

    @property
    def punctuator(self) -> SmartPunctuator:
        """Access punctuator for configuration."""
        return self._punctuator

    def add_post_processor(self, processor: Callable[[str], str]) -> None:
        """Add a custom post-processor to the pipeline."""
        self._post_processors.append(processor)

    def process(self, text: str) -> Tuple[str, List[CommandResult]]:
        """
        Process text through the full pipeline.

        Args:
            text: Raw transcribed text

        Returns:
            Tuple of (processed_text, executed_commands)
        """
        if not text:
            return text, []

        # Stage 1: Voice commands
        processed, commands = self._voice_commands.process(text)

        # Stage 2: Smart punctuation
        # Apply smart punctuation to enhance the text
        # Even when voice commands are used, we still want capitalization etc.
        # The punctuator is smart enough to not double-punctuate
        processed = self._punctuator.process(processed)

        # Stage 3: Custom post-processors
        for processor in self._post_processors:
            try:
                processed = processor(processed)
            except Exception as e:
                print(f"Post-processor error: {e}")

        return processed, commands

    def configure(
        self,
        enable_voice_commands: Optional[bool] = None,
        enable_smart_punctuation: Optional[bool] = None,
        remove_fillers: Optional[bool] = None,
        auto_capitalize: Optional[bool] = None,
        auto_periods: Optional[bool] = None,
        auto_commas: Optional[bool] = None
    ) -> None:
        """
        Configure pipeline settings.

        All parameters are optional - only provided values are updated.
        """
        if enable_voice_commands is not None:
            self._voice_commands.enabled = enable_voice_commands

        if enable_smart_punctuation is not None:
            self._punctuator.enabled = enable_smart_punctuation

        if remove_fillers is not None:
            self._punctuator.remove_fillers = remove_fillers

        if auto_capitalize is not None:
            self._punctuator.auto_capitalize = auto_capitalize

        if auto_periods is not None:
            self._punctuator.auto_periods = auto_periods

        if auto_commas is not None:
            self._punctuator.auto_commas = auto_commas

    def reset(self) -> None:
        """Reset pipeline state."""
        self._voice_commands.reset()


# Convenience function for simple usage
def process_transcription(
    text: str,
    enable_voice_commands: bool = True,
    enable_smart_punctuation: bool = True
) -> str:
    """
    Simple function to process transcribed text.

    Args:
        text: Raw transcribed text
        enable_voice_commands: Whether to process voice commands
        enable_smart_punctuation: Whether to add smart punctuation

    Returns:
        Processed text
    """
    pipeline = TextProcessingPipeline(
        enable_voice_commands=enable_voice_commands,
        enable_smart_punctuation=enable_smart_punctuation
    )
    processed, _ = pipeline.process(text)
    return processed


if __name__ == "__main__":
    # Test the text processor
    print("Testing Text Processor\n" + "=" * 50)

    # Test voice commands
    print("\n1. Voice Commands Test:")
    test_cases = [
        "hello world period how are you question mark",
        "this is a test new line and this is line two",
        "my email is john at sign example period com",
        "delete that I mean hello there",
        "open paren this is in parentheses close paren",
        "the code is open brace return true semicolon close brace",
    ]

    pipeline = TextProcessingPipeline()

    for test in test_cases:
        result, _ = pipeline.process(test)
        print(f"  Input:  '{test}'")
        print(f"  Output: '{result}'")
        print()

    # Test smart punctuation
    print("\n2. Smart Punctuation Test:")
    punct_tests = [
        "hello how are you i am fine thank you",
        "well i think we should go to the store and buy some groceries",
        "what time is it i need to leave soon",
        "first we need to plan then we execute finally we review",
    ]

    # Test with only smart punctuation (no voice commands)
    punct_pipeline = TextProcessingPipeline(enable_voice_commands=False)

    for test in punct_tests:
        result, _ = punct_pipeline.process(test)
        print(f"  Input:  '{test}'")
        print(f"  Output: '{result}'")
        print()

    print("\n3. Combined Test:")
    combined = "well i was thinking period what if we try something new question mark"
    result, cmds = pipeline.process(combined)
    print(f"  Input:  '{combined}'")
    print(f"  Output: '{result}'")
    print(f"  Commands: {[c.action.name for c in cmds]}")
