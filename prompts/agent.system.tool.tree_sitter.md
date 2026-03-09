### tree_sitter
use Tree-sitter for structure-aware code navigation and indexing
best for definitions references chunks scope and syntax queries
works on source files only and requires supported language detection

#### tree_sitter:symbols
extract symbols from one file
args path language(optional)
returns classes functions and other named definitions with spans and qualified names

#### tree_sitter:references
find references to a symbol within one file
args path symbol language(optional)
returns definitions and identifier references for the provided symbol name

#### tree_sitter:chunks
build syntax-aware chunks from one file
args path language(optional)
returns structured chunks labeled by symbol scope

#### tree_sitter:scope
find the smallest enclosing symbol scope for a location
args path line column language(optional)
returns the enclosing class/function/scope at the requested position

#### tree_sitter:query
run a Tree-sitter query against one file
args path query language(optional)
returns query matches and captures

#### tree_sitter:index
build or rebuild a structural index for a repository root or active project
args root_path(optional)
returns manifest summary with indexed files languages symbols and chunks

#### tree_sitter:lookup
search the structural index for a symbol
args symbol root_path(optional)
returns indexed symbol matches across the repo
