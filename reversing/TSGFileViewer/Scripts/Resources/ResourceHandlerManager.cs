using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Assets.Scripts.ResourceHandlers;
using UnityEngine;

namespace Assets.Scripts.Resources
{
    public class ResourceHandlerManager : MonoBehaviour
    {
	    private Dictionary<string, Type> ResourceHandlers = new()
	    {
		    { "CEC", typeof(ControllerEventConfig_Handler) },
		    { "EARS_MESH", typeof(EARS_MESH_Handler) },
		    { "LightTOC", typeof(LightTOC_Handler) },
		    { "MetaModel", typeof(MetaModel_Handler) },
		    { "rwID_TEXDICTIONARY", typeof(rwID_TEXDICTIONARY_Handler) },
		    { "SHK", typeof(ShockResource_Handler) },
		    { "TOB", typeof(TextOverlayFile_Handler) }
	    };

		private static Dictionary<string, IResourceHandler> ResourceHandlerInstances = new();

		private void Awake()
		{
			foreach (var item in ResourceHandlers)
			{
				var comp = gameObject.AddComponent(item.Value);
				ResourceHandlerInstances.Add(item.Key, (IResourceHandler)comp);
			}
		}

		public static bool HandlerExists(string id) => ResourceHandlerInstances.ContainsKey(id);

		public static IResourceHandler GetHandler(string id)
		{
			return ResourceHandlerInstances[id];
		}

		public static List<T> GetResources<T>() where T : Resource
		{
			var returnResources = new List<T>();

			foreach (var manager in ResourceHandlerInstances.Values)
			{
				var resources = manager.GetResources();

				if (!resources.Any())
				{
					continue;
				}

				returnResources.AddRange(resources.OfType<T>());
			}

			return returnResources;
		}

		public static Resource FindResourceById(Guid128 guid)
		{
			if (guid == null)
			{
				return null;
			}

			foreach (var manager in ResourceHandlerInstances.Values)
			{
				var resources = manager.GetResources();
				//Debug.Log($"Checking {manager.GetType().Name} - {resources.Count()} resources");

				foreach (var resource in resources)
				{
					//Debug.Log($"{(resource.GUID == null ? "NULL" : resource.GUID)} vs {guid}");

					if (resource.GUID == guid)
					{
						return resource;
					}
				}
			}

			return null;
		}
    }
}
