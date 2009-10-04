val init : string -> unit
module Dir :
  sig
    val db : unit -> string
    val log : unit -> string
    val static : unit -> string
    val port : unit -> int
  end
