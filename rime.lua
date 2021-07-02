socket = require('socket')
json = require('json')
host, port = "127.0.0.1", 51515

function connect_server()
   tcp = socket.tcp()
   tcp:settimeout(0.05)
   ok, err = tcp:connect(host, port)
   if not ok
   then error(err)
   end
   return tcp
end

tcp = socket.tcp()
tcp:settimeout(0)
tcp:connect(host, port)

function my_translator_impl(input, seg)
   local request = {request = "completion", input=input}
   local bytes = json:encode(request)
   local n = string.len(bytes)
   local head = tostring(n)
   assert(string.len(head) < 4)
   assert(tcp:send(string.rep('0', 4 - string.len(head)) .. tostring(n)))
   assert(tcp:send(bytes))
   head, _, _ = assert(tcp:receive(4))
   bytes, _, _ = assert(tcp:receive(tonumber(head)))
   return assert(json:decode(bytes))
end

function close_tcp()
   return tcp:close()
end

function my_translator(input, seg)
   local opt
   local ok, out = pcall(my_translator_impl, input, seg)
   if not ok
   then
      if tcp ~= nil then
         pcall(close_tcp)
      end
      ok, out = pcall(connect_server)
      if not ok then
         yield(Candidate(input, seg.start, seg._end, "", tostring(out)))
         return
      end
      tcp = out
      ok, out = pcall(my_translator_impl, input, seg)
      if not ok then
         yield(Candidate(input, seg.start, seg._end,  "", tostring(out)))
         return
      end
   end
   options = out
   for _, opt in ipairs(options) do
      yield(Candidate(input, seg.start, seg._end, opt[2], opt[1]))
   end
end
