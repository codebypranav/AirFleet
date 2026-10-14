"use client";

import { useState } from 'react';
import { useAction } from '@/components/Crew';
import { HeartIcon } from '@/components/Icons';
import type { FlightComment, Liked, Reply } from '@/types/flight';
import { addComment, deleteComment, editComment, getComments, likeComment } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const MAX_COMMENT = 500;

export function LikeButton({ liked, count, toggle }: { liked: boolean; count: number; toggle: (on: boolean) => Promise<Liked> }) {
    const [state, setState] = useState({ liked, like_count: count });
    const { busy, run } = useAction();
    return (
        <button
            type="button"
            onClick={() => run(() => toggle(!state.liked).then(setState))}
            disabled={busy}
            aria-pressed={state.liked}
            aria-label={state.liked ? 'Unlike' : 'Like'}
            className={`flex items-center gap-1 text-xs transition-colors ${state.liked ? 'text-clay' : 'text-ash hover:text-bone'}`}
        >
            <HeartIcon className="h-4 w-4" filled={state.liked} />
            {state.like_count > 0 && state.like_count}
        </button>
    );
}

function CommentForm({ initial = '', label, submit, onCancel }: {
    initial?: string;
    label: string;
    submit: (body: string) => Promise<unknown>;
    onCancel?: () => void;
}) {
    const [body, setBody] = useState(initial);
    const { busy, error, run } = useAction();
    const send = (e: React.FormEvent) => {
        e.preventDefault();
        run(() => submit(body.trim()).then(() => setBody('')));
    };
    return (
        <form onSubmit={send} className="mt-2">
            <div className="flex gap-2">
                <input
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    maxLength={MAX_COMMENT}
                    aria-label={label}
                    placeholder={label}
                    className="field-input py-1.5 text-sm"
                />
                <button type="submit" disabled={busy || !body.trim()} className="btn btn-primary py-1.5 text-sm">Send</button>
                {onCancel && <button type="button" onClick={onCancel} className="btn btn-ghost py-1.5 text-sm">Cancel</button>}
            </div>
            {error && <p className="alert-error mt-2" role="alert">{error}</p>}
        </form>
    );
}

function CommentRow({ comment, onReply, reload }: { comment: Reply; onReply?: () => void; reload: () => void }) {
    const [editing, setEditing] = useState(false);
    const { busy, error, run } = useAction();

    if (!comment.author) return <p className="py-1 text-sm italic text-ash">Comment deleted</p>;
    const remove = () => {
        if (window.confirm('Delete this comment?')) run(() => deleteComment(comment.id).then(reload));
    };
    return (
        <div className="py-1">
            {editing ? (
                <CommentForm
                    initial={comment.body}
                    label="Edit your comment"
                    submit={(body) => editComment(comment.id, body).then(() => { setEditing(false); reload(); })}
                    onCancel={() => setEditing(false)}
                />
            ) : (
                <p className="whitespace-pre-line text-sm text-bone">
                    <span className="mr-2 text-paper">{comment.author}</span>
                    {comment.body}
                </p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-ash">
                <span>{formatDate(comment.created_at)}{comment.edited && ' · edited'}</span>
                <LikeButton liked={comment.liked} count={comment.like_count} toggle={(on) => likeComment(comment.id, on)} />
                {onReply && <button type="button" onClick={onReply} className="hover:text-bone">Reply</button>}
                {comment.mine && !editing && <button type="button" onClick={() => setEditing(true)} className="hover:text-bone">Edit</button>}
                {comment.can_delete && <button type="button" onClick={remove} disabled={busy} className="hover:text-bone">Delete</button>}
            </div>
            {error && <p className="alert-error mt-2" role="alert">{error}</p>}
        </div>
    );
}

function Thread({ comment, flightId, reload }: { comment: FlightComment; flightId: number; reload: () => void }) {
    const [replying, setReplying] = useState(false);
    const reply = () => setReplying(true);
    return (
        <li className="py-2">
            <CommentRow comment={comment} onReply={comment.author ? reply : undefined} reload={reload} />
            {(comment.replies.length > 0 || replying) && (
                <div className="ml-5 border-l border-line pl-3">
                    {comment.replies.map((r) => <CommentRow key={r.id} comment={r} onReply={reply} reload={reload} />)}
                    {replying && (
                        <CommentForm
                            label="Write a reply"
                            submit={(body) => addComment(flightId, body, comment.id).then(() => { setReplying(false); reload(); })}
                            onCancel={() => setReplying(false)}
                        />
                    )}
                </div>
            )}
        </li>
    );
}

export function CommentList({ flightId }: { flightId: number }) {
    const { data: comments, error, reload } = useApi(() => getComments(flightId), `comments-${flightId}`);
    if (error) return <p className="alert-error mt-2" role="alert">{error}</p>;
    if (!comments) return <p className="mt-2 text-xs text-ash" role="status">Loading comments…</p>;
    return (
        <div className="mt-2">
            <ul className="divide-y divide-line/60">
                {comments.map((c) => <Thread key={c.id} comment={c} flightId={flightId} reload={reload} />)}
            </ul>
            <CommentForm label="Add a comment" submit={(body) => addComment(flightId, body).then(reload)} />
        </div>
    );
}

export function Comments({ flightId, count, startOpen = false }: { flightId: number; count: number; startOpen?: boolean }) {
    const [open, setOpen] = useState(startOpen);
    return (
        <div>
            <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="text-xs text-ash hover:text-bone">
                {open ? 'Hide comments' : count ? `View ${count} comment${count === 1 ? '' : 's'}` : 'Comment'}
            </button>
            {open && <CommentList flightId={flightId} />}
        </div>
    );
}
