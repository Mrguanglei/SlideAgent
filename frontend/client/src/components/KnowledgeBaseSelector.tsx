import React, { useEffect, useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, FileText, Link as LinkIcon, File } from "lucide-react";
import { getKnowledgeDocuments, type DocumentResponse } from "@/lib/api";
import { toast } from "sonner";

interface KnowledgeBaseSelectorProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSelect: (documents: DocumentResponse[]) => void;
}

export function KnowledgeBaseSelector({
    open,
    onOpenChange,
    onSelect,
}: KnowledgeBaseSelectorProps) {
    const [documents, setDocuments] = useState<DocumentResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedIds, setSelectedIds] = useState<number[]>([]);

    useEffect(() => {
        if (open) {
            loadDocuments();
            setSelectedIds([]); // Reset selection on open
        }
    }, [open]);

    const loadDocuments = async () => {
        setLoading(true);
        try {
            const docs = await getKnowledgeDocuments();
            setDocuments(docs);
        } catch (error) {
            console.error("Failed to load documents:", error);
            toast.error("Failed to load knowledge base documents");
        } finally {
            setLoading(false);
        }
    };

    const handleToggleSelect = (id: number) => {
        setSelectedIds((prev) =>
            prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
        );
    };

    const handleConfirm = () => {
        const selectedDocs = documents.filter((doc) => selectedIds.includes(doc.id));
        onSelect(selectedDocs);
        onOpenChange(false);
    };

    const getFileIcon = (type: string) => {
        if (type === "url") return <LinkIcon className="h-4 w-4 text-blue-500" />;
        if (type === "text") return <FileText className="h-4 w-4 text-gray-500" />;
        return <File className="h-4 w-4 text-purple-500" />;
    };

    const formatSize = (bytes: number) => {
        if (bytes === 0) return "--";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Select from Knowledge Base</DialogTitle>
                </DialogHeader>

                <div className="h-[300px] border rounded-md">
                    {loading ? (
                        <div className="h-full flex items-center justify-center">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : documents.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
                            No documents found
                        </div>
                    ) : (
                        <ScrollArea className="h-full">
                            <div className="p-4 space-y-2">
                                {documents.map((doc) => (
                                    <div
                                        key={doc.id}
                                        className="flex items-start space-x-3 p-2 rounded hover:bg-muted/50 cursor-pointer"
                                        onClick={() => handleToggleSelect(doc.id)}
                                    >
                                        <Checkbox
                                            checked={selectedIds.includes(doc.id)}
                                            onCheckedChange={() => handleToggleSelect(doc.id)}
                                            className="mt-1"
                                        />
                                        <div className="flex-1 overflow-hidden">
                                            <div className="flex items-center space-x-2">
                                                {getFileIcon(doc.file_type)}
                                                <span className="text-sm font-medium truncate">
                                                    {doc.display_name || doc.filename}
                                                </span>
                                            </div>
                                            <div className="flex items-center text-xs text-muted-foreground mt-1 space-x-2">
                                                <span>{doc.file_type}</span>
                                                <span>•</span>
                                                <span>{formatSize(doc.file_size)}</span>
                                                <span>•</span>
                                                <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleConfirm} disabled={selectedIds.length === 0}>
                        Confirm ({selectedIds.length})
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
