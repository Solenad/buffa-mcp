"""Debounce-based watcher refresh and branch-switch trigger behavior."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Callable, Optional, Set
from dataclasses import dataclass
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class WatchConfig:
    """Configuration for file system watcher."""
    enabled: bool = True
    debounce_ms: int = 500
    on_git_branch_switch: str = "reindex_changed"  # Options: "reindex_changed", "full_reindex", "none"
    watch_paths: list[str] = None
    
    def __post_init__(self):
        if self.watch_paths is None:
            self.watch_paths = ["./"]


class ChangeHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """Handles file system events with debouncing."""
    
    def __init__(self, 
                 callback: Callable[[Set[str]], None],
                 debounce_ms: int = 500):
        """
        Initialize change handler.
        
        Args:
            callback: Function to call when debounced changes occur
            debounce_ms: Debounce delay in milliseconds
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog package is required for file watching")
            
        super().__init__()
        self.callback = callback
        self.debounce_ms = debounce_ms
        self._debounce_timer: Optional[threading.Timer] = None
        self._pending_changes: Set[str] = set()
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def _schedule_callback(self) -> None:
        """Schedule the callback to run after debounce period."""
        with self._lock:
            # Cancel existing timer if any
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            # Schedule new callback
            self._debounce_timer = threading.Timer(
                self.debounce_ms / 1000.0,  # Convert ms to seconds
                self._execute_callback
            )
            self._debounce_timer.start()
            
            self.logger.debug(f"Scheduled callback in {self.debounce_ms}ms "
                            f"with {len(self._pending_changes)} pending changes")
    
    def _execute_callback(self) -> None:
        """Execute the callback with pending changes."""
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer = None
            
            changes = self._pending_changes.copy()
            self._pending_changes.clear()
        
        if changes:
            self.logger.info(f"Executing callback for {len(changes)} changed files")
            try:
                self.callback(changes)
            except Exception as e:
                self.logger.error(f"Error in watcher callback: {e}")
        else:
            self.logger.debug("Callback executed with no changes")
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            self._handle_event(event.src_path)
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self._handle_event(event.src_path)
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if not event.is_directory:
            self._handle_event(event.src_path)
    
    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move/rename events."""
        if not event.is_directory:
            # Handle both source and destination paths
            self._handle_event(event.src_path)
            self._handle_event(event.dest_path)
    
    def _handle_event(self, file_path: str) -> None:
        """Handle a file system event."""
        # Normalize path
        normalized_path = os.path.normpath(file_path)
        
        with self._lock:
            self._pending_changes.add(normalized_path)
        
        self.logger.debug(f"Queued {normalized_path} for processing "
                        f"(pending: {len(self._pending_changes)})")
        
        # Schedule callback
        self._schedule_callback()


class GitBranchWatcher:
    """Watches for Git branch switches and triggers appropriate actions."""
    
    def __init__(self, 
                 callback: Callable[[str, str], None],
                 check_interval: float = 1.0):
        """
        Initialize Git branch watcher.
        
        Args:
            callback: Function to call when branch changes (old_branch, new_branch)
            check_interval: How often to check for branch changes in seconds
        """
        self.callback = callback
        self.check_interval = check_interval
        self._current_branch: Optional[str] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.logger = logging.getLogger(__name__)
    
    def _get_current_branch(self) -> Optional[str]:
        """Get the current Git branch name."""
        try:
            # Try to get current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                # Handle detached HEAD state
                if branch == "HEAD":
                    # Get the commit hash instead
                    result = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                return branch
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # Not in a git repo or git not available
            pass
        return None
    
    def start(self) -> None:
        """Start watching for Git branch changes."""
        if self._watch_thread and self._watch_thread.is_alive():
            logger.warning("Git branch watcher is already running")
            return
            
        # Get initial branch
        self._current_branch = self._get_current_branch()
        logger.info(f"Initial Git branch: {self._current_branch}")
        
        # Start watch thread
        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()
        logger.info("Started Git branch watcher")
    
    def stop(self) -> None:
        """Stop watching for Git branch changes."""
        self._stop_event.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)
        logger.info("Stopped Git branch watcher")
    
    def _watch_loop(self) -> None:
        """Main watch loop for Git branch changes."""
        while not self._stop_event.is_set():
            try:
                time.sleep(self.check_interval)
                
                if self._stop_event.is_set():
                    break
                
                current_branch = self._get_current_branch()
                
                if current_branch != self._current_branch:
                    old_branch = self._current_branch
                    self._current_branch = current_branch
                    
                    logger.info(f"Git branch changed: {old_branch} -> {current_branch}")
                    
                    try:
                        self.callback(old_branch or "unknown", current_branch or "unknown")
                    except Exception as e:
                        logger.error(f"Error in Git branch callback: {e}")
                        
            except Exception as e:
                logger.error(f"Error in Git branch watch loop: {e}")
                time.sleep(self.check_interval)  # Continue watching despite errors


class IndexingWatcher:
    """Main watcher that coordinates file system and Git branch watching."""
    
    def __init__(self, 
                 index_callback: Callable[[Set[str]], None],
                 branch_callback: Optional[Callable[[str, str], None]] = None,
                 config: Optional[WatchConfig] = None):
        """
        Initialize indexing watcher.
        
        Args:
            index_callback: Function to call when files need reindexing
            branch_callback: Function to call when Git branch changes
            config: Watcher configuration
        """
        self.index_callback = index_callback
        self.branch_callback = branch_callback
        self.config = config or WatchConfig()
        self.file_handler: Optional[ChangeHandler] = None
        self.git_watcher: Optional[GitBranchWatcher] = None
        self.observer: Optional[Observer] = None
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> None:
        """Start watching for changes."""
        if not self.config.enabled:
            logger.info("File watching is disabled in config")
            return
            
        if not WATCHDOG_AVAILABLE:
            logger.error("watchdog package not available, cannot start file watcher")
            return
        
        logger.info("Starting indexing watcher...")
        
        # Start file system watcher
        self._start_file_watcher()
        
        # Start Git branch watcher if callback provided
        if self.branch_callback:
            self._start_git_watcher()
        
        logger.info("Indexing watcher started")
    
    def stop(self) -> None:
        """Stop watching for changes."""
        logger.info("Stopping indexing watcher...")
        
        # Stop Git branch watcher
        if self.git_watcher:
            self.git_watcher.stop()
            self.git_watcher = None
        
        # Stop file system watcher
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.observer = None
        
        if self.file_handler:
            self.file_handler = None
        
        logger.info("Indexing watcher stopped")
    
    def _start_file_watcher(self) -> None:
        """Start the file system watcher."""
        self.file_handler = ChangeHandler(
            callback=self._on_file_changes,
            debounce_ms=self.config.debounce_ms
        )
        
        self.observer = Observer()
        
        # Watch each specified path
        for watch_path in self.config.watch_paths:
            path_obj = Path(watch_path)
            if path_obj.exists():
                self.observer.schedule(
                    self.file_handler,
                    str(path_obj.absolute()),
                    recursive=True
                )
                logger.info(f"Watching path: {path_obj.absolute()}")
            else:
                logger.warning(f"Watch path does not exist: {watch_path}")
        
        self.observer.start()
    
    def _start_git_watcher(self) -> None:
        """Start the Git branch watcher."""
        self.git_watcher = GitBranchWatcher(
            callback=self._on_git_branch_change,
            check_interval=1.0
        )
        self.git_watcher.start()
    
    def _on_file_changes(self, changed_files: Set[str]) -> None:
        """Handle file system changes."""
        self.logger.info(f"File watcher detected {len(changed_files)} changes")
        try:
            self.index_callback(changed_files)
        except Exception as e:
            self.logger.error(f"Error in file change callback: {e}")
    
    def _on_git_branch_change(self, old_branch: str, new_branch: str) -> None:
        """Handle Git branch changes."""
        self.logger.info(f"Git branch watcher detected change: {old_branch} -> {new_branch}")
        
        # Handle based on configuration
        if self.config.on_git_branch_switch == "none":
            self.logger.info("Ignoring Git branch switch per configuration")
            return
        elif self.config.on_git_branch_switch == "full_reindex":
            self.logger.info("Triggering full reindex due to Git branch switch")
            # TODO: Implement full reindex signal
        elif self.config.on_git_branch_switch == "reindex_changed":
            self.logger.info("Triggering reindex of changed files due to Git branch switch")
            # For now, we'll treat this as a file change event
            # In a full implementation, we might want to get the actual changed files
            # between branches using git diff
            try:
                # Get list of files that differ between branches
                result = subprocess.run(
                    ["git", "diff", "--name-only", old_branch, new_branch],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    changed_files = set()
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            changed_files.add(line.strip())
                    
                    if changed_files:
                        self.logger.info(f"Git branch switch affected {len(changed_files)} files")
                        self.index_callback(changed_files)
                    else:
                        self.logger.info("No file changes detected between branches")
                else:
                    self.logger.warning("Failed to get diff between branches, falling back to file watcher")
                    # Fall back to letting the file watcher handle actual file changes
            except Exception as e:
                self.logger.error(f"Error processing Git branch switch: {e}")
                # Fall back to normal file watching
        else:
            self.logger.warning(f"Unknown on_git_branch_switch value: {self.config.on_git_branch_switch}")


def create_indexing_watcher(index_callback: Callable[[Set[str]], None],
                          branch_callback: Optional[Callable[[str, str], None]] = None,
                          config: Optional[WatchConfig] = None) -> IndexingWatcher:
    """
    Factory function to create an IndexingWatcher instance.
    
    Args:
        index_callback: Function to call when files need reindexing
        branch_callback: Function to call when Git branch changes
        config: Watcher configuration
        
    Returns:
        Configured IndexingWatcher instance
    """
    return IndexingWatcher(
        index_callback=index_callback,
        branch_callback=branch_callback,
        config=config
    )


# Convenience functions for common use cases
def start_watching(index_callback: Callable[[Set[str]], None],
                  debounce_ms: int = 500,
                  watch_paths: Optional[list[str]] = None) -> IndexingWatcher:
    """
    Start watching for file changes with default settings.
    
    Args:
        index_callback: Function to call when files need reindexing
        debounce_ms: Debounce delay in milliseconds
        watch_paths: Paths to watch (defaults to ["./"])
        
    Returns:
        Started IndexingWatcher instance
    """
    config = WatchConfig(
        enabled=True,
        debounce_ms=debounce_ms,
        watch_paths=watch_paths or ["./"]
    )
    
    watcher = create_indexing_watcher(index_callback, None, config)
    watcher.start()
    return watcher


def start_watching_with_git(index_callback: Callable[[Set[str]], None],
                           branch_callback: Callable[[str, str], None],
                           debounce_ms: int = 500,
                           on_git_branch_switch: str = "reindex_changed",
                           watch_paths: Optional[list[str]] = None) -> IndexingWatcher:
    """
    Start watching for both file changes and Git branch switches.
    
    Args:
        index_callback: Function to call when files need reindexing
        branch_callback: Function to call when Git branch changes
        debounce_ms: Debounce delay in milliseconds
        on_git_branch_switch: How to handle Git branch switches
        watch_paths: Paths to watch (defaults to ["./"])
        
    Returns:
        Started IndexingWatcher instance
    """
    config = WatchConfig(
        enabled=True,
        debounce_ms=debounce_ms,
        on_git_branch_switch=on_git_branch_switch,
        watch_paths=watch_paths or ["./"]
    )
    
    watcher = create_indexing_watcher(index_callback, branch_callback, config)
    watcher.start()
    return watcher